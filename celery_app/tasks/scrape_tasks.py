from celery_app.celery import celery
from celery import chain
from datetime import datetime
import logging
from app.extensions import db
from app.models.website import Website
from app.models.product import Product
from app.models.product_snapshot import ProductSnapshot
from app.scraping.scraper_factory import ScraperFactory
from celery_app.tasks.index_tasks import index_product
from celery_app.tasks.alert_tasks import evaluate_alerts

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3)
def scrape_product(self, product_id, user_id=None):
    """Scrape a single product and create a snapshot."""
    logger.info(f'Scraping product {product_id}')
    
    try:
        from app import create_app
        app = create_app()
        
        with app.app_context():
            product = Product.query.get(product_id)
            if not product:
                logger.error(f'Product {product_id} not found')
                return {'success': False, 'error': 'Product not found'}
            
            website = Website.query.get(product.website_id)
            if not website:
                logger.error(f'Website {product.website_id} not found')
                return {'success': False, 'error': 'Website not found'}
            
            # Use factory to get site-specific scraper
            scraper = ScraperFactory.create_scraper(website.id, website.base_url)
            if not scraper:
                logger.error(f'No scraper available for {website.base_url}')
                return {'success': False, 'error': 'No scraper available for this website'}
            
            # ChampsSports takes a full URL; other scrapers take the last URL segment as SKU
            if 'champssports.com' in website.base_url.lower():
                detail_key = product.url
            else:
                # Strip URL fragment (#colourWayId-... on ASOS) before extracting segment
                clean_url = product.url.split('#')[0].rstrip('/')
                detail_key = clean_url.split('/')[-1]
            data = scraper.extract_product_details(detail_key)
            if not data:
                logger.warning(f'No data returned for product {product_id} (key={detail_key})')
                return {'success': False, 'error': 'Scrape failed'}

            # Update product-level fields only when present in response
            # (ASOS extract_product_details returns variants-only; ShopWSS returns full product)
            new_price = data.get('price')
            if new_price:
                product.price_previous = product.price_current
                product.price_current = new_price
                product.last_price_change = datetime.utcnow()
            if data.get('title') or data.get('name'):
                product.title = data.get('title') or data.get('name')
            if data.get('image') or data.get('imageUrl'):
                product.image = data.get('image') or data.get('imageUrl')
            if data.get('brand'):
                product.brand = data['brand']
            if data.get('availability'):
                product.availability = data['availability']
            if data.get('available') is not None:
                product.available = data['available']
            if data.get('inventoryLevel') is not None:
                product.inventory_level = data['inventoryLevel']
            product.last_seen = datetime.utcnow()

            # Snapshot price: fall back to current stored price when not in response (ASOS variants-only)
            snapshot_price = new_price or (float(product.price_current) if product.price_current else None)
            snapshot = ProductSnapshot(
                product_id=product_id,
                price=snapshot_price,
                currency=data.get('currency', 'USD'),
                availability=data.get('availability') or product.availability,
                extra_data={
                    'inventoryLevel': data.get('inventoryLevel'),
                    'available': data.get('available'),
                }
            )
            db.session.add(snapshot)

            # Upsert variants (works for both ASOS and ShopWSS)
            if data.get('variants'):
                from celery_app.tasks.discovery_tasks import update_product_with_details
                update_product_with_details(product, data)

                # Derive product-level availability from variants when scraper didn't return it
                if not data.get('availability'):
                    variants = data['variants']
                    any_in_stock = any(v.get('available') for v in variants)
                    all_out = all(not v.get('available') for v in variants)
                    total_inv = sum(v.get('inventoryLevel') or 0 for v in variants)
                    product.available = any_in_stock
                    product.availability = 'InStock' if any_in_stock else 'OutOfStock'
                    if total_inv > 0:
                        product.inventory_level = total_inv
                    # Update snapshot availability too
                    snapshot.availability = product.availability

            db.session.commit()

            logger.info(f'Successfully scraped product {product_id}, snapshot {snapshot.id}')

            return {
                'success': True,
                'product_id': product_id,
                'snapshot_id': snapshot.id
            }
            
    except Exception as e:
        logger.exception(f'Error scraping product {product_id}: {e}')
        self.retry(countdown=60, exc=e)
        raise


@celery.task(bind=True, max_retries=3)
def scrape_product_batch(self, website_id, urls):
    logger.info(f'Scraping {len(urls)} products for website {website_id}')
    
    try:
        from app import create_app
        app = create_app()
        
        with app.app_context():
            website = Website.query.get(website_id)
            if not website:
                logger.error(f'Website {website_id} not found')
                return {'status': 'error', 'message': 'Website not found'}
            
            scraper = ProductScraper(website)
            
            scraped_count = 0
            updated_count = 0
            new_count = 0
            
            for url in urls:
                try:
                    data = scraper.scrape(url)
                    if not data:
                        logger.warning(f'Failed to scrape {url}')
                        continue
                    
                    product = Product.query.filter_by(
                        website_id=website_id,
                        url=url
                    ).first()
                    
                    if not product:
                        product = Product(
                            website_id=website_id,
                            url=url,
                            title=data.get('title'),
                            brand=data.get('brand'),
                            sku=data.get('sku'),
                            image=data.get('image'),
                            categories=data.get('categories', [])
                        )
                        db.session.add(product)
                        db.session.flush()
                        new_count += 1
                    else:
                        latest_snapshot = ProductSnapshot.query.filter_by(
                            product_id=product.id
                        ).order_by(ProductSnapshot.created_at.desc()).first()
                        
                        if latest_snapshot and latest_snapshot.hash == data['hash']:
                            logger.debug(f'No changes for {url}, skipping')
                            continue
                        
                        product.title = data.get('title')
                        product.brand = data.get('brand')
                        product.sku = data.get('sku')
                        product.image = data.get('image')
                        product.categories = data.get('categories', [])
                        product.updated_at = datetime.utcnow()
                        updated_count += 1
                    
                    # Strip currency symbols from price for numeric field
                    price_value = data.get('price')
                    if price_value:
                        price_str = str(price_value).replace('$', '').replace('€', '').replace('£', '').replace(',', '').strip()
                        try:
                            price_value = float(price_str)
                        except (ValueError, TypeError):
                            price_value = None
                    
                    snapshot = ProductSnapshot(
                        product_id=product.id,
                        price=price_value,
                        currency=data.get('currency', 'USD'),
                        availability=data.get('availability'),
                        hash=data['hash'],
                        extra_data=data
                    )
                    db.session.add(snapshot)
                    db.session.commit()
                    
                    chain(
                        index_product.s(product.id),
                        evaluate_alerts.s(product.id, snapshot.id)
                    ).apply_async(queue='index_queue')
                    
                    scraped_count += 1
                    
                except Exception as e:
                    logger.error(f'Error scraping {url}: {e}')
                    db.session.rollback()
                    continue
            
            logger.info(f'Scraped {scraped_count} products for website {website_id} (new: {new_count}, updated: {updated_count})')
            
            return {
                'status': 'success',
                'scraped': scraped_count,
                'new': new_count,
                'updated': updated_count
            }
            
    except Exception as e:
        logger.error(f'Error in scrape_product_batch task: {e}')
        raise
