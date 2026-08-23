from celery import Celery
from celery.schedules import crontab

from shared.config import get_settings
from shared.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = Celery(
    "pulsestream",
    broker=settings.celery_broker_url,
    backend=settings.celery_broker_url,
    include=["services.celery_worker.tasks"],
)

app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    beat_schedule={
        "hourly-summaries": {
            "task": "pulsestream.hourly_summaries",
            "schedule": crontab(minute=5),
        },
        "daily-summaries": {
            "task": "pulsestream.daily_summaries",
            "schedule": crontab(hour=0, minute=15),
        },
        "cleanup-expired-keys": {
            "task": "pulsestream.cleanup_expired_keys",
            "schedule": crontab(minute=20),
        },
        "failure-report": {
            "task": "pulsestream.failure_report",
            "schedule": crontab(minute=10),
        },
        "recompute-aggregates": {
            "task": "pulsestream.recompute_aggregates",
            "schedule": crontab(hour=0, minute=30),
        },
    },
)
