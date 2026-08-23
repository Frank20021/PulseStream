from datetime import datetime

from shared.analytics import keys

ENGAGEMENT_TYPES = {
    "profile_view",
    "post_view",
    "post_like",
    "post_comment",
    "connection_request",
}


def apply_event_counters(
    pipeline,
    *,
    event_type: str,
    user_id: str,
    target_id: str,
    device: str | None,
    source: str | None,
    when: datetime,
) -> None:
    minute = keys.minute_bucket(when)
    hour = keys.hour_bucket(when)

    pipeline.incr(keys.events_total_key())
    pipeline.incr(keys.events_count_key(minute))
    pipeline.expire(keys.events_count_key(minute), keys.MINUTE_TTL_SECONDS)
    pipeline.incr(keys.events_type_key(event_type, minute))
    pipeline.expire(keys.events_type_key(event_type, minute), keys.MINUTE_TTL_SECONDS)
    pipeline.sadd(keys.active_users_key(minute), user_id)
    pipeline.expire(keys.active_users_key(minute), keys.MINUTE_TTL_SECONDS)

    if event_type in ENGAGEMENT_TYPES:
        pipeline.incr(keys.engagement_key(minute))
        pipeline.expire(keys.engagement_key(minute), keys.MINUTE_TTL_SECONDS)

    if device:
        token = keys.sanitize_token(device)
        pipeline.sadd("devices:seen", token)
        pipeline.incr(keys.device_count_key(token, minute))
        pipeline.expire(keys.device_count_key(token, minute), keys.MINUTE_TTL_SECONDS)

    if source:
        token = keys.sanitize_token(source)
        pipeline.sadd("sources:seen", token)
        pipeline.incr(keys.source_count_key(token, minute))
        pipeline.expire(keys.source_count_key(token, minute), keys.MINUTE_TTL_SECONDS)

    if event_type == "connection_request":
        pipeline.incr(keys.connection_requests_key(hour))
        pipeline.expire(keys.connection_requests_key(hour), keys.HOUR_TTL_SECONDS)

    if event_type == "post_view":
        pipeline.sadd("posts:seen", target_id)
        pipeline.incr(keys.post_views_key(target_id))
        pipeline.zincrby(keys.trending_posts_key(minute), 1, target_id)
        pipeline.expire(keys.trending_posts_key(minute), keys.TRENDING_TTL_SECONDS)

    if event_type == "job_view":
        pipeline.sadd("jobs:seen", target_id)
        pipeline.incr(keys.job_views_key(target_id))
        pipeline.incr(keys.job_views_total_key())

    if event_type == "job_click":
        pipeline.sadd("jobs:seen", target_id)
        pipeline.incr(keys.job_clicks_key(target_id))
        pipeline.incr(keys.job_clicks_total_key())
        pipeline.zincrby(keys.trending_jobs_key(minute), 1, target_id)
        pipeline.expire(keys.trending_jobs_key(minute), keys.TRENDING_TTL_SECONDS)

    if event_type == "job_save":
        pipeline.sadd("jobs:seen", target_id)
        pipeline.incr(keys.job_saves_key(target_id))
