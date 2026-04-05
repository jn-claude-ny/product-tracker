"""
Tracked Product Tasks - Priority-based product checking
Handles crawling individual tracked products based on priority and crawl_period_hours
"""
from celery_app.celery import celery
from app import create_app
from app.extensions import db
from app.models.tracked_product import TrackedProduct
from app.models.product import Product
from app.models.product_snapshot import ProductSnapshot
from celery_app.tasks.scrape_tasks import scrape_product
from celery_app.tasks.alert_tasks import evaluate_tracked_product_alerts
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

PRIORITY_MAP = {
    'now': 'urgent_now',
    'urgent': 'urgent_now',
    'high': 'high_priority',
    'moderate': 'moderate_priority',
    'normal': 'normal_priority'
}


def get_queue_for_priority(priority):
    """Get the appropriate queue name for a priority level."""
    return PRIORITY_MAP.get(priority, 'normal_priority')


@celery.task(bind=True, max_retries=3)
def check_tracked_product(self, tracked_product_id):
    """
    Check a single tracked product - scrape and evaluate alerts.
    This is the main task that gets dispatched based on priority.
    """
    app = create_app()
    with app.app_context():
        tracked = TrackedProduct.query.get(tracked_product_id)
        if not tracked:
            logger.warning(f"Tracked product {tracked_product_id} not found")
            return {'error': 'Tracked product not found'}
        
        # Check if product still exists
        product = Product.query.get(tracked.product_id)
        if not product:
            logger.warning(f"Product {tracked.product_id} not found for tracked product {tracked_product_id}")
            return {'error': 'Product not found'}
        
        try:
            # Scrape the product
            logger.info(f"Checking tracked product {product.title} (priority: {tracked.priority})")
            result = scrape_product.delay(product.id, tracked.user_id)
            
            # Wait for scrape to complete and get result
            scrape_result = result.get(timeout=60)
            
            if scrape_result.get('success'):
                # Evaluate alerts based on new snapshot
                snapshot_id = scrape_result.get('snapshot_id')
                if snapshot_id:
                    evaluate_tracked_product_alerts.delay(tracked.product_id, snapshot_id)
                
                # Update last checked time
                tracked.updated_at = datetime.utcnow()
                db.session.commit()
                
                return {
                    'success': True,
                    'product_id': tracked.product_id,
                    'tracked_product_id': tracked_product_id,
                    'snapshot_id': snapshot_id
                }
            else:
                logger.error(f"Scrape failed for tracked product {tracked_product_id}: {scrape_result.get('error')}")
                return {'error': scrape_result.get('error', 'Scrape failed')}
                
        except Exception as e:
            logger.exception(f"Error checking tracked product {tracked_product_id}: {e}")
            self.retry(countdown=60, exc=e)
            raise


@celery.task(bind=True, max_retries=3)
def check_tracked_product_now(self, tracked_product_id):
    """Check tracked product immediately - bypasses all queues."""
    return check_tracked_product(tracked_product_id)


@celery.task(bind=True, max_retries=3)
def check_tracked_product_urgent(self, tracked_product_id):
    """Check tracked product with urgent priority."""
    return check_tracked_product(tracked_product_id)


@celery.task(bind=True, max_retries=3)
def check_tracked_product_high(self, tracked_product_id):
    """Check tracked product with high priority."""
    return check_tracked_product(tracked_product_id)


@celery.task(bind=True, max_retries=3)
def check_tracked_product_moderate(self, tracked_product_id):
    """Check tracked product with moderate priority."""
    return check_tracked_product(tracked_product_id)


@celery.task(bind=True, max_retries=3)
def check_tracked_product_normal(self, tracked_product_id):
    """Check tracked product with normal priority."""
    return check_tracked_product(tracked_product_id)


@celery.task(bind=True)
def schedule_tracked_products_check():
    """
    Main scheduler task - runs periodically and dispatches tracked product checks
    based on crawl_period_hours and priority.
    """
    app = create_app()
    with app.app_context():
        now = datetime.utcnow()
        
        # Get all tracked products that need checking
        # A product needs checking if: now >= (updated_at + crawl_period_hours)
        tracked_products = TrackedProduct.query.all()
        
        scheduled_count = 0
        for tracked in tracked_products:
            # Calculate next check time
            last_check = tracked.updated_at or tracked.created_at
            next_check = last_check + timedelta(hours=tracked.crawl_period_hours or 24)
            
            # Check if it's time to run
            if now >= next_check:
                # Dispatch to appropriate queue based on priority
                priority = tracked.priority or 'normal'
                queue = get_queue_for_priority(priority)
                
                # Route to correct task based on priority
                if priority in ['now', 'urgent']:
                    check_tracked_product_now.apply_async(
                        args=[tracked.id],
                        queue=queue,
                        priority=0  # Highest priority
                    )
                elif priority == 'high':
                    check_tracked_product_high.apply_async(
                        args=[tracked.id],
                        queue=queue,
                        priority=1
                    )
                elif priority == 'moderate':
                    check_tracked_product_moderate.apply_async(
                        args=[tracked.id],
                        queue=queue,
                        priority=5
                    )
                else:  # normal
                    check_tracked_product_normal.apply_async(
                        args=[tracked.id],
                        queue=queue,
                        priority=10
                    )
                
                scheduled_count += 1
                logger.info(f"Scheduled tracked product {tracked.id} (priority: {priority}, queue: {queue})")
        
        logger.info(f"Scheduled {scheduled_count} tracked products for checking")
        return {'scheduled': scheduled_count}


@celery.task(bind=True)
def trigger_tracked_product_now(self, tracked_product_id):
    """
    Manually trigger a tracked product check immediately.
    This bypasses the crawl_period_hours check.
    """
    app = create_app()
    with app.app_context():
        tracked = TrackedProduct.query.get(tracked_product_id)
        if not tracked:
            return {'error': 'Tracked product not found'}
        
        # Force immediate check
        tracked.priority = 'now'
        db.session.commit()
        
        # Dispatch to urgent_now queue with highest priority
        result = check_tracked_product_now.apply_async(
            args=[tracked_product_id],
            queue='urgent_now',
            priority=0
        )
        
        logger.info(f"Triggered immediate check for tracked product {tracked_product_id}")
        return {
            'success': True,
            'tracked_product_id': tracked_product_id,
            'task_id': result.id
        }
