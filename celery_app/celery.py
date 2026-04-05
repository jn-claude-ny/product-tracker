from celery import Celery
from app.config import Config

celery = Celery(
    'product_tracker',
    broker=Config.CELERY_BROKER_URL,
    backend=Config.CELERY_RESULT_BACKEND,
    include=[
        'celery_app.tasks.crawl_tasks',
        'celery_app.tasks.scrape_tasks',
        'celery_app.tasks.discovery_tasks',
        'celery_app.tasks.alert_tasks',
        'celery_app.tasks.index_tasks'
    ]
)

celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3000,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_max_retries=3,
    task_routes={
        'celery_app.tasks.crawl_tasks.*': {'queue': 'crawl_queue'},
        'celery_app.tasks.scrape_tasks.*': {'queue': 'scrape_queue'},
        'celery_app.tasks.discovery_tasks.*': {'queue': 'scrape_queue'},
        'celery_app.tasks.alert_tasks.*': {'queue': 'alert_queue'},
        'celery_app.tasks.index_tasks.*': {'queue': 'index_queue'},
    },
    beat_scheduler='celery_app.beat_scheduler:DynamicScheduler',
    beat_schedule={}
)
