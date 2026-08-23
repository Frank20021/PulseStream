import logging
from datetime import datetime, timedelta, timezone

from redis import Redis

from shared.config import get_settings

logger = logging.getLogger(__name__)

STALE_MINUTE_PREFIXES = (
    "events:count:",
    "events:type:",
    "events:device:",
    "events:source:",
    "active_users:",
    "engagement:",
    "trending:posts:",
    "trending:jobs:",
)


def _parse_minute_suffix(key: str, prefix: str) -> datetime | None:
    suffix = key[len(prefix) :]
    # events:type:{event_type}:{minute} has an extra segment
    if prefix == "events:type:":
        parts = suffix.rsplit(":", 1)
        if len(parts) != 2:
            return None
        suffix = parts[1]
    elif prefix in {"events:device:", "events:source:"}:
        parts = suffix.rsplit(":", 1)
        if len(parts) != 2:
            return None
        suffix = parts[1]
    try:
        return datetime.strptime(suffix, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def cleanup_expired_keys() -> dict:
    settings = get_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    repaired = 0
    deleted = 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)

    try:
        for key in client.scan_iter("processed:event:*"):
            ttl = client.ttl(key)
            if ttl == -1:
                client.expire(key, settings.idempotency_ttl_seconds)
                repaired += 1

        for prefix in STALE_MINUTE_PREFIXES:
            for key in client.scan_iter(f"{prefix}*"):
                moment = _parse_minute_suffix(key, prefix)
                if moment is not None and moment < cutoff:
                    client.delete(key)
                    deleted += 1
    finally:
        client.close()

    logger.info("cleanup_complete", extra={"repaired_ttl": repaired, "deleted_stale": deleted})
    return {"repaired_ttl": repaired, "deleted_stale": deleted}
