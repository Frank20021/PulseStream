import logging

from celery.signals import worker_ready

from services.celery_worker.celery_app import app
from shared.aggregates import (
    cleanup_expired_keys as run_cleanup,
)
from shared.aggregates import (
    generate_daily_summaries as run_daily,
)
from shared.aggregates import (
    generate_hourly_summaries as run_hourly,
)
from shared.aggregates import (
    recompute_redis_from_postgres as run_recompute,
)
from shared.aggregates import (
    write_failure_report as run_failure_report,
)
from shared.recommendations.service import ensure_catalog

logger = logging.getLogger(__name__)


@worker_ready.connect
def _create_tables(**_kwargs) -> None:
    ensure_catalog()
    logger.info("celery_worker_ready")


@app.task(name="pulsestream.hourly_summaries")
def generate_hourly_summaries(hour_iso: str | None = None) -> dict:
    return run_hourly(hour_iso)


@app.task(name="pulsestream.daily_summaries")
def generate_daily_summaries(day_iso: str | None = None) -> dict:
    return run_daily(day_iso)


@app.task(name="pulsestream.cleanup_expired_keys")
def cleanup_expired_keys() -> dict:
    return run_cleanup()


@app.task(name="pulsestream.recompute_aggregates")
def recompute_aggregates() -> dict:
    return run_recompute()


@app.task(name="pulsestream.failure_report")
def failure_report(hours: int = 24) -> dict:
    return run_failure_report(hours)
