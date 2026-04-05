from celery_app.celery import celery
from celery import group
from sqlalchemy.orm import Session
from datetime import datetime
import logging
from app.extensions import db
from app.models.website import Website
from app.models.product import Product
from app.scraping.sitemap_parser import SitemapParser
from app.scraping.scraper_factory import ScraperFactory
from celery_app.tasks.scrape_tasks import scrape_product_batch
from celery_app.tasks.discovery_tasks import discover_products_task

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3)
def crawl_website(self, website_id, force_full_crawl=False):
    logger.info(f'Crawling website {website_id}, force_full_crawl={force_full_crawl}')
    
    try:
        from app import create_app
        app = create_app()
        
        with app.app_context():
            website = Website.query.get(website_id)
            if not website:
                logger.error(f'Website {website_id} not found')
                return {'status': 'error', 'message': 'Website not found'}
            
            # Check if this is a supported multi-site scraper
            if ScraperFactory.is_supported(website.base_url):
                logger.info(f'Using multi-site scraper for {website.base_url}')
                
                # Set state to crawling
                website.crawl_state = 'crawling'
                website.is_crawling = True
                website.crawl_progress = 0
                website.products_discovered = 0
                website.products_processed = 0
                website.sitemap_last_checked = datetime.utcnow()
                db.session.commit()
                
                # Queue discovery tasks for both genders
                tasks = []
                for gender in ['men', 'women']:
                    tasks.append(discover_products_task.s(website_id, gender))
                
                job = group(tasks)
                job.apply_async()
                
                logger.info(f'Queued {len(tasks)} discovery tasks for website {website_id}')
                
                return {
                    'status': 'success',
                    'method': 'multi-site-scraper',
                    'discovery_tasks_queued': len(tasks)
                }
            
            # Fall back to legacy sitemap-based crawling
            
            try:
                parser = SitemapParser()
                
                try:
                    urls_data, new_etag, new_last_modified = parser.parse_all(
                        website.sitemap_url,
                        etag=website.sitemap_etag if not force_full_crawl else None,
                        last_modified=website.sitemap_last_checked.isoformat() if website.sitemap_last_checked and not force_full_crawl else None,
                        proxy_group=website.proxy_group,
                        use_cache=not force_full_crawl
                    )
                    
                    if new_etag:
                        website.sitemap_etag = new_etag
                    website.sitemap_last_checked = datetime.utcnow()
                    website.last_error = None
                    website.last_error_at = None
                    db.session.commit()
                    
                except Exception as e:
                    logger.error(f'Error parsing sitemap for website {website_id}: {e}')
                    website.is_crawling = False
                    website.current_task_id = None
                    website.last_error = str(e)
                    website.last_error_at = datetime.utcnow()
                    db.session.commit()
                    raise self.retry(exc=e, countdown=300)
                
                if not urls_data:
                    logger.info(f'No URLs found for website {website_id}')
                    website.is_crawling = False
                    website.current_task_id = None
                    db.session.commit()
                    return {'status': 'success', 'urls_processed': 0}
                
                urls_to_scrape = []
                
                if force_full_crawl:
                    urls_to_scrape = [url for url, _ in urls_data]
                else:
                    existing_products = {
                        p.url: p for p in Product.query.filter_by(website_id=website_id).all()
                    }
                    
                    for url, lastmod in urls_data:
                        if url not in existing_products:
                            urls_to_scrape.append(url)
                        elif lastmod:
                            try:
                                lastmod_dt = datetime.fromisoformat(lastmod.replace('Z', '+00:00'))
                                if existing_products[url].updated_at < lastmod_dt:
                                    urls_to_scrape.append(url)
                            except Exception:
                                urls_to_scrape.append(url)
                
                if not urls_to_scrape:
                    logger.info(f'No new or updated URLs for website {website_id}')
                    website.is_crawling = False
                    website.current_task_id = None
                    db.session.commit()
                    return {'status': 'success', 'urls_processed': 0}
                
                batch_size = 100
                batches = [urls_to_scrape[i:i + batch_size] for i in range(0, len(urls_to_scrape), batch_size)]
                
                tasks = []
                for batch in batches:
                    tasks.append(scrape_product_batch.s(website_id, batch))
                
                job = group(tasks)
                job.apply_async()
                
                logger.info(f'Enqueued {len(batches)} batches ({len(urls_to_scrape)} URLs) for website {website_id}')
                
                # Reset crawling state after enqueueing batches
                website.is_crawling = False
                website.current_task_id = None
                db.session.commit()
                
                return {
                    'status': 'success',
                    'urls_processed': len(urls_to_scrape),
                    'batches': len(batches)
                }
            
            except Exception as e:
                # Reset state on any error
                website.is_crawling = False
                website.current_task_id = None
                website.last_error = str(e)
                website.last_error_at = datetime.utcnow()
                db.session.commit()
                raise
            
    except Exception as e:
        logger.error(f'Error in crawl_website task: {e}')
        raise
