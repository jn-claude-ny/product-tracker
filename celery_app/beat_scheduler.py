from celery.beat import Scheduler, ScheduleEntry
from celery import current_app
from celery.schedules import crontab
from datetime import datetime
from croniter import croniter
import logging

logger = logging.getLogger(__name__)


class DynamicScheduleEntry(ScheduleEntry):
    """Custom schedule entry that properly wraps our dynamic tasks."""
    
    def __init__(self, name, task, schedule, args=None, kwargs=None,
                 last_run_at=None, total_run_count=0, options=None, **extra):
        super().__init__(
            name=name,
            task=task,
            schedule=schedule,
            args=args,
            kwargs=kwargs or {},
            last_run_at=last_run_at,
            total_run_count=total_run_count,
            options=options or {},
            **extra
        )


class DynamicScheduler(Scheduler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_check = datetime.utcnow()
        self._schedule = {}
        self._load_schedule()

    def _load_schedule(self):
        try:
            from app import create_app
            from app.models.website import Website
            
            app = create_app()
            with app.app_context():
                websites = Website.query.filter(Website.cron_schedule.isnot(None)).all()
                
                new_schedule = {}
                for website in websites:
                    if website.cron_schedule:
                        try:
                            parts = website.cron_schedule.split()
                            if len(parts) == 5:
                                minute, hour, day_of_month, month, day_of_week = parts
                                
                                schedule_name = f'crawl_website_{website.id}'
                                new_schedule[schedule_name] = DynamicScheduleEntry(
                                    name=schedule_name,
                                    task='celery_app.tasks.crawl_tasks.crawl_website',
                                    schedule=crontab(
                                        minute=minute,
                                        hour=hour,
                                        day_of_month=day_of_month,
                                        month_of_year=month,
                                        day_of_week=day_of_week
                                    ),
                                    args=(website.id, False)
                                )
                        except Exception as e:
                            logger.error(f'Error parsing cron schedule for website {website.id}: {e}')
                
                self._schedule = new_schedule
                logger.info(f'Loaded {len(new_schedule)} scheduled tasks')
                
        except Exception as e:
            logger.error(f'Error loading schedule: {e}')

    def tick(self):
        now = datetime.utcnow()
        
        if (now - self.last_check).total_seconds() > 60:
            self._load_schedule()
            self.last_check = now
        
        return super().tick()

    @property
    def schedule(self):
        return self._schedule

    def setup_schedule(self):
        pass
