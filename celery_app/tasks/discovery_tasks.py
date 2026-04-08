"""
Product Discovery Tasks
Handles product discovery for multi-site tracking using site-specific scrapers.
"""
from celery_app.celery import celery
from celery import group
from datetime import datetime
import logging
from app.extensions import db
from app.models.website import Website
from app.models.product import Product
from app.models.product_snapshot import ProductSnapshot
from app.scraping.scraper_factory import ScraperFactory

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3, queue='scrape_queue')
def discover_products_task(self, website_id: int, gender: str, limit: int = None):
    """
    Discover products for a website using appropriate scraper.
    
    Args:
        website_id: Database ID of website
        gender: 'men' or 'women'
        limit: Optional limit on products to discover
    """
    logger.info(f'Starting product discovery for website {website_id}, gender={gender}')
    
    try:
        from app import create_app
        app = create_app()
        
        with app.app_context():
            website = Website.query.get(website_id)
            if not website:
                logger.error(f'Website {website_id} not found')
                return {'status': 'error', 'message': 'Website not found'}
            
            # Create appropriate scraper
            scraper = ScraperFactory.create_scraper(website_id, website.base_url)
            if not scraper:
                logger.error(f'No scraper available for {website.base_url}')
                return {'status': 'error', 'message': 'Unsupported website'}
            
            try:
                # Discover products
                products = scraper.discover_products(gender, limit)
                logger.info(f'Discovered {len(products)} products for website {website_id}')
                logger.info(f'Products type: {type(products)}, First product sample: {products[0] if products else "None"}')
                
                if not products:
                    return {'status': 'success', 'products_discovered': 0}
                
                # Update website with total expected products
                website.total_products_expected = (website.total_products_expected or 0) + len(products)
                db.session.commit()

                # Store products — variants already included in each hit
                stored_count = 0
                logger.info(f'Starting to store {len(products)} products...')
                for idx, product_data in enumerate(products):
                    try:
                        if idx < 3:  # Log first 3 for debugging
                            logger.info(f'Processing product {idx+1}: {product_data.get("id") or product_data.get("sku")}')
                        normalized = scraper.normalize_product_data(product_data, gender)
                        # Carry variants through normalisation (not part of standard normalize output)
                        normalized['variants'] = product_data.get('variants', [])
                        product = upsert_product(website_id, normalized)
                        if product:
                            stored_count += 1
                    except Exception as e:
                        logger.error(f'Error storing product: {e}', exc_info=True)

                # Mark crawl complete (single-pass — no detail extraction needed)
                website.products_discovered = (website.products_discovered or 0) + stored_count
                website.products_processed = (website.products_processed or 0) + stored_count
                website.crawl_progress = 100
                website.crawl_state = 'completed'
                website.is_crawling = False
                website.current_task_id = None
                website.last_crawl_completed_at = datetime.utcnow()
                db.session.commit()

                logger.info(f'Stored {stored_count} products (variants included). Crawl complete.')

                scraper.close()

                return {
                    'status': 'success',
                    'products_discovered': len(products),
                    'products_stored': stored_count,
                }
                
            except Exception as e:
                logger.error(f'Error during discovery: {e}')
                scraper.close()
                raise self.retry(exc=e, countdown=300)
                
    except Exception as e:
        logger.error(f'Error in discover_products_task: {e}')
        raise


@celery.task(bind=True, max_retries=3)
def extract_product_details_batch(self, website_id: int, product_ids: list):
    """
    Extract detailed information for a batch of products.
    
    Args:
        website_id: Database ID of website
        product_ids: List of product IDs to extract details for
    """
    logger.info(f'Extracting details for {len(product_ids)} products from website {website_id}')
    
    try:
        from app import create_app
        app = create_app()
        
        with app.app_context():
            website = Website.query.get(website_id)
            if not website:
                logger.error(f'Website {website_id} not found')
                return {'status': 'error', 'message': 'Website not found'}
            
            # Check if crawl is paused - abort task if so
            if website.crawl_state == 'paused':
                logger.info(f'Crawl is paused for website {website_id}, aborting task')
                return {'status': 'aborted', 'message': 'Crawl is paused'}
            
            scraper = ScraperFactory.create_scraper(website_id, website.base_url)
            if not scraper:
                logger.error(f'No scraper available for {website.base_url}')
                return {'status': 'error', 'message': 'Unsupported website'}
            
            success_count = 0
            error_count = 0
            
            for product_id in product_ids:
                try:
                    # Extract detailed info
                    details = scraper.extract_product_details(str(product_id))
                    
                    if details:
                        # Find product in database
                        product = Product.query.filter_by(
                            website_id=website_id,
                            sku=str(product_id)
                        ).first()
                        
                        if product:
                            # Update product with detailed info
                            update_product_with_details(product, details)
                            success_count += 1
                        else:
                            logger.warning(f'Product {product_id} not found in database')
                    
                    # Rate limiting
                    scraper.rate_limit(0.3)
                    
                except Exception as e:
                    logger.error(f'Error extracting details for product {product_id}: {e}')
                    error_count += 1
            
            scraper.close()
            
            # Update progress
            website.products_processed = (website.products_processed or 0) + success_count
            
            # Calculate progress (50% for discovery, 50% for detail extraction)
            if website.total_products_expected > 0:
                discovery_progress = 50  # Discovery is complete
                detail_progress = int((website.products_processed / website.total_products_expected) * 50)
                website.crawl_progress = discovery_progress + detail_progress
                
                # Mark as completed if all products processed
                if website.products_processed >= website.total_products_expected:
                    website.crawl_state = 'completed'
                    website.is_crawling = False
                    website.current_task_id = None
                    website.last_crawl_completed_at = datetime.utcnow()
                    website.crawl_progress = 100
            
            db.session.commit()
            
            logger.info(f'Detail extraction complete: {success_count} success, {error_count} errors. Progress: {website.crawl_progress}%')
            
            return {
                'status': 'success',
                'products_processed': len(product_ids),
                'success_count': success_count,
                'error_count': error_count
            }
            
    except Exception as e:
        logger.error(f'Error in extract_product_details_batch: {e}')
        raise


def upsert_product(website_id: int, product_data: dict) -> Product:
    """
    Create or update a product in the database.
    
    Args:
        website_id: Database ID of website
        product_data: Normalized product data
        
    Returns:
        Product instance
    """
    try:
        logger.info(f"Upserting product: sku={product_data.get('sku')}, title={product_data.get('title')[:50] if product_data.get('title') else 'N/A'}")
        # Find existing product by SKU or URL
        product = None
        if product_data.get('sku'):
            product = Product.query.filter_by(
                website_id=website_id,
                sku=product_data['sku']
            ).first()
        
        if not product and product_data.get('url'):
            product = Product.query.filter_by(
                website_id=website_id,
                url=product_data['url']
            ).first()
        
        if product:
            # Update existing product
            old_price = product.price_current

            product.title = product_data.get('title') or product.title
            product.brand = product_data.get('brand') or product.brand
            product.image = product_data.get('image') or product.image
            product.gender = product_data.get('gender') or product.gender
            product.category = product_data.get('category')
            product.color = product_data.get('color')

            # Handle price updates
            new_price = product_data.get('price_current')
            if new_price and new_price != product.price_current:
                product.price_previous = product.price_current
                product.price_current = new_price
                product.last_price_change = datetime.utcnow()
            elif new_price:
                product.price_current = new_price

            product.currency = product_data.get('currency', 'USD')
            product.is_on_sale = product_data.get('is_on_sale', False)
            product.is_new = product_data.get('is_new', False)
            product.categories = product_data.get('categories', [])
            product.availability = product_data.get('availability') or product.availability
            product.available = product_data.get('available') if product_data.get('available') is not None else product.available
            product.inventory_level = product_data.get('inventoryLevel') if product_data.get('inventoryLevel') is not None else product.inventory_level
            product.last_seen = datetime.utcnow()
            product.updated_at = datetime.utcnow()

            # Create snapshot if price changed
            if old_price != product.price_current and product.price_current:
                snapshot = ProductSnapshot(
                    product_id=product.id,
                    price=product.price_current,
                    availability=product.availability
                )
                db.session.add(snapshot)
        else:
            # Create new product
            product = Product(
                website_id=website_id,
                url=product_data.get('url', ''),
                sku=product_data.get('sku'),
                title=product_data.get('title'),
                brand=product_data.get('brand'),
                image=product_data.get('image'),
                gender=product_data.get('gender'),
                category=product_data.get('category'),
                color=product_data.get('color'),
                price_current=product_data.get('price_current'),
                currency=product_data.get('currency', 'USD'),
                is_on_sale=product_data.get('is_on_sale', False),
                is_new=product_data.get('is_new', False),
                categories=product_data.get('categories', []),
                availability=product_data.get('availability'),
                available=product_data.get('available'),
                inventory_level=product_data.get('inventoryLevel'),
                first_seen=datetime.utcnow(),
                last_seen=datetime.utcnow()
            )
            db.session.add(product)
            db.session.flush()  # Flush to get product.id without committing

            # Create initial snapshot if price exists
            if product.price_current:
                snapshot = ProductSnapshot(
                    product_id=product.id,
                    price=product.price_current,
                    availability=product.availability
                )
                db.session.add(snapshot)
        
        db.session.commit()
        logger.info(f"✅ Successfully saved product: id={product.id}, sku={product.sku}")

        # Upsert variants if present (they come straight from the GraphQL hit)
        if product_data.get('variants'):
            update_product_with_details(product, product_data)

        return product
        
    except Exception as e:
        logger.error(f'Error upserting product (sku={product_data.get("sku")}): {e}', exc_info=True)
        db.session.rollback()
        return None


def update_product_with_details(product: Product, details: dict):
    """
    Update product with variant/detail information from a scraper hit.

    Args:
        product: Product instance
        details: Normalised product data (may include 'variants' list)
    """
    try:
        if details.get('color'):
            product.color = details['color']

        if details.get('variants'):
            from app.models.product_variant import ProductVariant

            for variant_data in details['variants']:
                variant_sku = variant_data.get('sku', '')
                if not variant_sku:
                    continue

                variant = ProductVariant.query.filter_by(
                    product_id=product.id,
                    variant_sku=str(variant_sku)
                ).first()

                is_in_stock = variant_data.get('available', False)
                availability_text = variant_data.get('availability', 'Unknown')

                if variant:
                    variant.size = variant_data.get('size')
                    variant.color = variant_data.get('color')
                    variant.price = variant_data.get('price')
                    variant.stock_state = availability_text
                    variant.available = is_in_stock
                    variant.inventory_level = variant_data.get('inventoryLevel')
                    variant.last_checked = datetime.utcnow()
                    if is_in_stock:
                        variant.last_in_stock = datetime.utcnow()
                    variant.updated_at = datetime.utcnow()
                else:
                    variant = ProductVariant(
                        product_id=product.id,
                        variant_sku=str(variant_sku),
                        size=variant_data.get('size'),
                        color=variant_data.get('color'),
                        price=variant_data.get('price'),
                        stock_state=availability_text,
                        available=is_in_stock,
                        inventory_level=variant_data.get('inventoryLevel'),
                        last_checked=datetime.utcnow(),
                        first_seen=datetime.utcnow(),
                        last_in_stock=datetime.utcnow() if is_in_stock else None
                    )
                    db.session.add(variant)

        product.updated_at = datetime.utcnow()
        db.session.commit()

    except Exception as e:
        logger.error(f'Error updating product with details: {e}')
        db.session.rollback()
