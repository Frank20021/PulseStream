import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

KEY_PREFIX = "processed:event:"


class IdempotencyStore:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    def key(self, event_id: str) -> str:
        return f"{KEY_PREFIX}{event_id}"

    async def already_processed(self, event_id: str) -> bool:
        try:
            return await self._redis.get(self.key(event_id)) is not None
        except RedisError:
            logger.warning(
                "idempotency_check_failed",
                extra={"event_id": event_id, "outcome": "continue"},
            )
            return False

    async def mark_processed(self, event_id: str) -> None:
        try:
            await self._redis.set(self.key(event_id), "1", ex=self._ttl_seconds)
        except RedisError:
            logger.warning(
                "idempotency_mark_failed",
                extra={"event_id": event_id, "outcome": "continue"},
            )
