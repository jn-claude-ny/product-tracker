"""
tracked_product_tasks.py
------------------------
Manages the check lifecycle for products a user is specifically tracking
(TrackedProduct rows). This is separate from bulk site crawls.

TASK CHAIN (the whole flow for one tracked product check):

  trigger_tracked_product_now(tracked_product_id)   <- API call or scheduler
    -> _dispatch_check_chain()
         -> chain(
              scrape_product(product_id),           <- scrape_queue worker
              on_scrape_complete(tracked_product_id) <- alert_queue worker
            ).apply_async()
                -> evaluate_tracked_product_alerts() <- alert_queue worker
                     -> send_discord_alert()         <- alert_queue worker

WHY A CHAIN instead of calling tasks sequentially:
  Celery workers must NOT block waiting for another task's result (.get() inside a
  task causes deadlocks). Instead, `chain()` passes the return value of each task
  as the first argument to the next task automatically and asynchronously.

PRIORITY QUEUES:
  Five separate worker containers each listen on their own queue:
    urgent_now        -> check_tracked_product_now / trigger_tracked_product_now
    high_priority     -> check_tracked_product_high
    moderate_priority -> check_tracked_product_moderate
    normal_priority   -> check_tracked_product_normal

  The priority is stored on TrackedProduct.priority and maps via PRIORITY_MAP.
  schedule_tracked_products_check() runs every 5 minutes (via celery beat) and
  dispatches each due product to its correct queue.
"""
from celery import chain
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

# Maps TrackedProduct.priority string -> Celery queue name
# Queue names must match docker-compose.yml worker command -Q flags
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
    Check a single tracked product — fire scrape then chain alert evaluation.
    Uses Celery chain to avoid blocking result.get() inside a task.
    """
    app = create_app()
    with app.app_context():
        tracked = TrackedProduct.query.get(tracked_product_id)
        if not tracked:
            logger.warning(f"Tracked product {tracked_product_id} not found")
            return {'error': 'Tracked product not found'}

        product = Product.query.get(tracked.product_id)
        if not product:
            logger.warning(f"Product {tracked.product_id} not found for tracked product {tracked_product_id}")
            return {'error': 'Product not found'}

        logger.info(f"Checking tracked product {product.title} (priority: {tracked.priority})")

        # Use a chain: scrape → on_scrape_complete (which calls evaluate_alerts)
        # This avoids blocking result.get() inside a worker task.
        task_chain = chain(
            scrape_product.s(product.id, tracked.user_id),
            on_scrape_complete.s(tracked_product_id),
        )
        task_chain.apply_async(queue='scrape_queue')

        return {'success': True, 'product_id': tracked.product_id, 'tracked_product_id': tracked_product_id}


@celery.task(bind=True, max_retries=3)
def on_scrape_complete(self, scrape_result, tracked_product_id):
    """
    Chain callback: called after scrape_product finishes.
    Receives scrape_result dict, evaluates alerts, updates tracked product timestamp.
    """
    app = create_app()
    with app.app_context():
        if not scrape_result or not scrape_result.get('success'):
            logger.warning(
                f"Scrape failed for tracked_product {tracked_product_id}: "
                f"{scrape_result.get('error') if scrape_result else 'no result'}"
            )
            return {'error': 'Scrape failed'}

        snapshot_id = scrape_result.get('snapshot_id')
        product_id  = scrape_result.get('product_id')

        tracked = TrackedProduct.query.get(tracked_product_id)
        if tracked:
            tracked.updated_at = datetime.utcnow()
            db.session.commit()

        if snapshot_id:
            logger.info(
                f"Scrape succeeded for tracked_product {tracked_product_id} "
                f"(product {product_id}, snapshot {snapshot_id}). Evaluating alerts."
            )
            evaluate_tracked_product_alerts.apply_async(
                args=[product_id, snapshot_id],
                queue='alert_queue'
            )

        return {'success': True, 'tracked_product_id': tracked_product_id,
                'product_id': product_id, 'snapshot_id': snapshot_id}


def _dispatch_check_chain(tracked_product_id):
    """
    Helper: build and dispatch the scrape → on_scrape_complete chain for a tracked product.
    Returns a result dict immediately; alert evaluation happens asynchronously.
    """
    from app import create_app
    from app.models.tracked_product import TrackedProduct
    from app.models.product import Product
    app = create_app()
    with app.app_context():
        tracked = TrackedProduct.query.get(tracked_product_id)
        if not tracked:
            logger.warning(f"Tracked product {tracked_product_id} not found")
            return {'error': 'Tracked product not found'}
        product = Product.query.get(tracked.product_id)
        if not product:
            logger.warning(f"Product {tracked.product_id} not found")
            return {'error': 'Product not found'}
        logger.info(f"Dispatching chain for tracked product {product.title} (priority: {tracked.priority})")
        task_chain = chain(
            scrape_product.s(product.id, tracked.user_id),
            on_scrape_complete.s(tracked_product_id),
        )
        task_chain.apply_async(queue='scrape_queue')
        return {'success': True, 'product_id': tracked.product_id, 'tracked_product_id': tracked_product_id}


@celery.task(bind=True, max_retries=3)
def check_tracked_product_now(self, tracked_product_id):
    """Check tracked product immediately."""
    return _dispatch_check_chain(tracked_product_id)


@celery.task(bind=True, max_retries=3)
def check_tracked_product_urgent(self, tracked_product_id):
    """Check tracked product with urgent priority."""
    return _dispatch_check_chain(tracked_product_id)


@celery.task(bind=True, max_retries=3)
def check_tracked_product_high(self, tracked_product_id):
    """Check tracked product with high priority."""
    return _dispatch_check_chain(tracked_product_id)


@celery.task(bind=True, max_retries=3)
def check_tracked_product_moderate(self, tracked_product_id):
    """Check tracked product with moderate priority."""
    return _dispatch_check_chain(tracked_product_id)


@celery.task(bind=True, max_retries=3)
def check_tracked_product_normal(self, tracked_product_id):
    """Check tracked product with normal priority."""
    return _dispatch_check_chain(tracked_product_id)


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
    Bypasses crawl_period_hours — dispatches scrape → alert chain directly.
    """
    logger.info(f"Triggered immediate check for tracked product {tracked_product_id}")
    result = _dispatch_check_chain(tracked_product_id)
    return {'success': True, 'tracked_product_id': tracked_product_id, **result}
