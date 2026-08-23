import logging

from redis import Redis
from sqlalchemy import select

from shared.analytics.counters import apply_event_counters
from shared.config import get_settings
from shared.database import Event
from shared.database.session import open_session

logger = logging.getLogger(__name__)

ANALYTICS_PATTERNS = (
    "metrics:*",
    "events:count:*",
    "events:type:*",
    "events:device:*",
    "events:source:*",
    "active_users:*",
    "engagement:*",
    "connection_requests:*",
    "trending:*",
    "post:*",
    "job:*",
    "jobs:seen",
    "posts:seen",
    "devices:seen",
    "sources:seen",
)


def _clear_analytics(client: Redis) -> int:
    deleted = 0
    for pattern in ANALYTICS_PATTERNS:
        keys = list(client.scan_iter(pattern))
        if keys:
            deleted += client.delete(*keys)
    return deleted


def recompute_redis_from_postgres() -> dict:
    settings = get_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    session = open_session()
    replayed = 0
    try:
        deleted = _clear_analytics(client)
        pipeline = client.pipeline()
        for event in session.execute(select(Event).order_by(Event.received_at.asc())).scalars():
            metadata = event.metadata_ or {}
            when = event.processed_at or event.received_at
            apply_event_counters(
                pipeline,
                event_type=event.event_type,
                user_id=event.user_id,
                target_id=event.target_id,
                device=metadata.get("device"),
                source=metadata.get("source"),
                when=when,
            )
            replayed += 1
            if replayed % 100 == 0:
                pipeline.execute()
                pipeline = client.pipeline()
        if replayed % 100 != 0:
            pipeline.execute()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        client.close()

    logger.info("aggregates_recomputed", extra={"replayed": replayed, "cleared": deleted})
    return {"replayed": replayed, "cleared": deleted}
