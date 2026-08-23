import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from shared.analytics import keys
from shared.analytics.counters import apply_event_counters
from shared.schemas import ActivityEvent

logger = logging.getLogger(__name__)


class AnalyticsWriter:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def record(self, event: ActivityEvent) -> None:
        pipeline = self._redis.pipeline()
        apply_event_counters(
            pipeline,
            event_type=event.event_type.value,
            user_id=event.user_id,
            target_id=event.target_id,
            device=event.metadata.device,
            source=event.metadata.source,
            when=keys.utc_now(),
        )
        try:
            await pipeline.execute()
        except RedisError:
            logger.warning(
                "analytics_update_failed",
                extra={"event_id": str(event.event_id), "event_type": event.event_type.value},
            )
            raise

    async def record_ops(self, *, duplicates: int = 0, dead_letters: int = 0, retries: int = 0) -> None:
        pipeline = self._redis.pipeline()
        if duplicates:
            pipeline.incrby(keys.duplicates_total_key(), duplicates)
        if dead_letters:
            pipeline.incrby(keys.dead_letters_total_key(), dead_letters)
        if retries:
            pipeline.incrby(keys.retries_total_key(), retries)
        try:
            await pipeline.execute()
        except RedisError:
            logger.warning("ops_metrics_update_failed")
