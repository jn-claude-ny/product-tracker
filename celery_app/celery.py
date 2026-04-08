from celery import Celery
from app.config import Config

# ---------------------------------------------------------------------------
# Celery Application
# ---------------------------------------------------------------------------
# This is the central Celery instance shared by every worker container.
# All worker containers (crawl, scrape, alert, index, priority workers)
# import THIS object from celery_app.celery.
#
# HOW WORKERS ARE STARTED (see docker-compose.yml):
#   celery_worker_crawl   -> listens on crawl_queue
#   celery_worker_scrape  -> listens on scrape_queue  (--pool=solo, single-threaded)
#   celery_worker_alert   -> listens on alert_queue
#   celery_worker_index   -> listens on index_queue
#   celery_worker_urgent_now, high_priority, moderate_priority, normal_priority
#                         -> each listens on its own queue for tracked-product checks
#   celery_beat           -> the scheduler that fires periodic tasks
# ---------------------------------------------------------------------------

celery = Celery(
    'product_tracker',
    broker=Config.CELERY_BROKER_URL,       # Redis acts as message broker
    backend=Config.CELERY_RESULT_BACKEND,  # Redis also stores task results
    include=[
        # Each module is eagerly imported by every worker so all tasks are
        # registered and can receive messages from any queue.
        'celery_app.tasks.crawl_tasks',
        'celery_app.tasks.scrape_tasks',
        'celery_app.tasks.discovery_tasks',
        'celery_app.tasks.alert_tasks',
        'celery_app.tasks.index_tasks',
        'celery_app.tasks.tracked_product_tasks'
    ]
)

celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,       # Tasks show STARTED state in Flower
    task_time_limit=3600,          # Hard kill after 1 hour (prevents zombie tasks)
    task_soft_time_limit=3000,     # Raises SoftTimeLimitExceeded at 50 min so task can clean up
    worker_prefetch_multiplier=1,  # Each worker fetches ONE task at a time (important for scraping)
    worker_max_tasks_per_child=1000,  # Restart worker process after 1000 tasks (memory leak prevention)
    task_acks_late=True,           # ACK only after task completes — safe retry on worker crash
    task_reject_on_worker_lost=True,  # Re-queue task if worker dies mid-execution
    task_default_retry_delay=60,   # Wait 60s before retrying a failed task
    task_max_retries=3,

    # ---------------------------------------------------------------------------
    # TASK ROUTING
    # ---------------------------------------------------------------------------
    # Routes determine which queue a task is placed in when dispatched.
    # Each worker container only listens on its own queue, so routing controls
    # which physical worker container actually executes each task.
    #
    # IMPORTANT: on_scrape_complete must route to alert_queue, NOT scrape_queue.
    # It's part of a Celery chain (scrape_product -> on_scrape_complete) but
    # it does alert logic, not scraping. Without this explicit route it would
    # inherit scrape_queue from scrape_tasks.* wildcard and never reach the
    # alert worker.
    # ---------------------------------------------------------------------------
    task_routes={
        'celery_app.tasks.crawl_tasks.*':      {'queue': 'crawl_queue'},
        'celery_app.tasks.scrape_tasks.*':     {'queue': 'scrape_queue'},
        'celery_app.tasks.discovery_tasks.*':  {'queue': 'scrape_queue'},
        'celery_app.tasks.alert_tasks.*':      {'queue': 'alert_queue'},
        'celery_app.tasks.index_tasks.*':      {'queue': 'index_queue'},
        # Priority-based tracked product queues — each maps to a dedicated worker
        'celery_app.tasks.tracked_product_tasks.trigger_tracked_product_now':      {'queue': 'urgent_now'},
        'celery_app.tasks.tracked_product_tasks.check_tracked_product_now':        {'queue': 'urgent_now'},
        'celery_app.tasks.tracked_product_tasks.check_tracked_product_urgent':     {'queue': 'urgent_now'},
        'celery_app.tasks.tracked_product_tasks.check_tracked_product_high':       {'queue': 'high_priority'},
        'celery_app.tasks.tracked_product_tasks.check_tracked_product_moderate':   {'queue': 'moderate_priority'},
        'celery_app.tasks.tracked_product_tasks.check_tracked_product_normal':     {'queue': 'normal_priority'},
        'celery_app.tasks.tracked_product_tasks.schedule_tracked_products_check':  {'queue': 'urgent_now'},
        # on_scrape_complete is the chain callback after scrape_product finishes.
        # It must run on the alert worker, not the scrape worker.
        'celery_app.tasks.tracked_product_tasks.on_scrape_complete':               {'queue': 'alert_queue'},
    },

    # ---------------------------------------------------------------------------
    # BEAT SCHEDULER
    # ---------------------------------------------------------------------------
    # celery_app.beat_scheduler:DynamicScheduler reads cron schedules from the
    # database so you can change them without restarting the beat container.
    # The built-in beat_schedule below fires the tracked-products dispatcher
    # every 5 minutes; it compares each TrackedProduct.updated_at against
    # its crawl_period_hours to decide whether a new check is due.
    # ---------------------------------------------------------------------------
    beat_scheduler='celery_app.beat_scheduler:DynamicScheduler',
    beat_schedule={
        'schedule-tracked-products': {
            'task': 'celery_app.tasks.tracked_product_tasks.schedule_tracked_products_check',
            'schedule': 300.0,  # Every 5 minutes
        },
    }
)
