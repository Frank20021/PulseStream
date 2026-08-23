from datetime import datetime, timedelta, timezone

MINUTE_TTL_SECONDS = 7200
HOUR_TTL_SECONDS = 172800
TRENDING_TTL_SECONDS = 600


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def minute_bucket(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def hour_bucket(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")


def iter_minute_buckets(moment: datetime, count: int) -> list[str]:
    start = moment.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return [minute_bucket(start - timedelta(minutes=offset)) for offset in range(count)]


def iter_hour_buckets(moment: datetime, count: int) -> list[str]:
    start = moment.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return [hour_bucket(start - timedelta(hours=offset)) for offset in range(count)]


def sanitize_token(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_." else "_" for char in value.strip())
    return (cleaned[:50] or "unknown")


def events_total_key() -> str:
    return "metrics:events:total"


def events_count_key(minute: str) -> str:
    return f"events:count:{minute}"


def events_type_key(event_type: str, minute: str) -> str:
    return f"events:type:{event_type}:{minute}"


def active_users_key(minute: str) -> str:
    return f"active_users:{minute}"


def engagement_key(minute: str) -> str:
    return f"engagement:{minute}"


def device_count_key(device: str, minute: str) -> str:
    return f"events:device:{device}:{minute}"


def source_count_key(source: str, minute: str) -> str:
    return f"events:source:{source}:{minute}"


def connection_requests_key(hour: str) -> str:
    return f"connection_requests:{hour}"


def post_views_key(post_id: str) -> str:
    return f"post:{post_id}:views"


def job_views_key(job_id: str) -> str:
    return f"job:{job_id}:views"


def job_clicks_key(job_id: str) -> str:
    return f"job:{job_id}:clicks"


def job_saves_key(job_id: str) -> str:
    return f"job:{job_id}:saves"


def trending_posts_key(minute: str) -> str:
    return f"trending:posts:{minute}"


def trending_jobs_key(minute: str) -> str:
    return f"trending:jobs:{minute}"


def job_views_total_key() -> str:
    return "metrics:job_views"


def job_clicks_total_key() -> str:
    return "metrics:job_clicks"


def duplicates_total_key() -> str:
    return "metrics:duplicates:total"


def dead_letters_total_key() -> str:
    return "metrics:dead_letters:total"


def retries_total_key() -> str:
    return "metrics:retries:total"


def consumer_lag_key() -> str:
    return "metrics:consumer_lag"
