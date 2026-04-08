# ---------------------------------------------------------------------------
# scrape_tasks.py
# ---------------------------------------------------------------------------
# Responsible for fetching up-to-date product details (price, availability,
# variants/sizes) for a SINGLE product that already exists in the database.
#
# This is NOT discovery (finding new products) — that is crawl_tasks.py /
# discovery_tasks.py. This task is called AFTER a product has been found and
# stored, to keep its data fresh and to feed the alert pipeline.
#
# FLOW:
#   scrape_product(product_id)
#     └─ ScraperFactory.create_scraper()         <- picks the right scraper class
#     └─ scraper.extract_product_details(key)    <- fetches live data from the site
#     └─ update_product fields                    <- price, availability, inventory
#     └─ ProductSnapshot created                  <- immutable point-in-time record
#     └─ update_product_with_details()            <- upserts ProductVariant rows
#     └─ derives product-level availability       <- aggregated from variants
#     └─ returns {success, product_id, snapshot_id}
#
# The result dict is then consumed by on_scrape_complete (tracked_product_tasks)
# which triggers alert evaluation.
# ---------------------------------------------------------------------------

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
    """
    Scrape a single product and create a point-in-time snapshot.

    Called by:
      - check_tracked_product (via Celery chain: scrape_product -> on_scrape_complete)
      - Manually via API (POST /api/tracked-products/<id>/run)

    Returns dict: {'success': True/False, 'product_id': ..., 'snapshot_id': ...}
    This return value is automatically passed as the first argument to the
    next task in the chain (on_scrape_complete).
    """
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
            
            # ScraperFactory inspects website.base_url and returns the right scraper:
            #   champssports.com -> ChampsSportsScraper
            #   shopwss.com      -> ShopWssScraper
            #   asos.com         -> AsosScraper
            scraper = ScraperFactory.create_scraper(website.id, website.base_url)
            if not scraper:
                logger.error(f'No scraper available for {website.base_url}')
                return {'success': False, 'error': 'No scraper available for this website'}
            
            # ---------------------------------------------------------------------------
            # DETAIL KEY — what we pass to extract_product_details()
            # ---------------------------------------------------------------------------
            # Each scraper's extract_product_details() expects a different identifier:
            #
            #   ChampsSports  -> full product page URL
            #                    e.g. https://www.champssports.com/product/nike-air-max/1234.html
            #
            #   ASOS          -> numeric product ID (last segment of URL, fragment stripped)
            #                    e.g. product URL: .../prd/37463#colourWayId-123
            #                         detail_key:  '37463'
            #                    NOTE: ASOS URLs often have a #colourWayId-... fragment
            #                    that must be stripped before splitting on '/'.
            #
            #   ShopWSS       -> product SKU / last URL segment
            # ---------------------------------------------------------------------------
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

            # ---------------------------------------------------------------------------
            # UPDATE PRODUCT-LEVEL FIELDS
            # ---------------------------------------------------------------------------
            # Scrapers return different subsets of fields:
            #   ASOS    -> variants only (no top-level price/availability)
            #   ShopWSS -> full product data including price + availability
            #   Champs  -> variants + top-level price + availability
            #
            # We only overwrite a field if the scraper actually returned it,
            # so a partial response never clears existing data.
            # ---------------------------------------------------------------------------
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

            # ---------------------------------------------------------------------------
            # CREATE SNAPSHOT
            # ---------------------------------------------------------------------------
            # A ProductSnapshot is an immutable record of the product state at this
            # moment in time. The alert system compares consecutive snapshots to detect
            # changes (price drop, back-in-stock, etc.).
            #
            # snapshot_price: use price from scraper response; fall back to the current
            # stored price when the scraper returns variants-only (ASOS case).
            # ---------------------------------------------------------------------------
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

            # ---------------------------------------------------------------------------
            # UPSERT VARIANTS
            # ---------------------------------------------------------------------------
            # update_product_with_details() creates or updates ProductVariant rows
            # (one per size/colorway) from the variants list returned by the scraper.
            # Each variant has: sku, size, color, price, available, inventoryLevel.
            #
            # ASOS SPECIAL CASE:
            # The ASOS scraper returns variants but NOT a top-level availability field.
            # So after upserting variants we aggregate them to derive the product-level
            # availability: if ANY variant is available -> InStock, else OutOfStock.
            # inventory_level = sum of all variant inventory quantities.
            # We also backfill snapshot.availability with the derived value.
            # ---------------------------------------------------------------------------
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
                    # Update snapshot availability too so alert evaluation sees the right value
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
