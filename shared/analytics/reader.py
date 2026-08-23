from datetime import datetime

from redis.asyncio import Redis

from shared.analytics import keys
from shared.analytics.metrics import click_through_rate, merge_scores


def _as_int(value: str | int | None) -> int:
    if value is None:
        return 0
    return int(value)


class AnalyticsReader:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def summary(self, minutes: int = 5, limit: int = 5) -> dict:
        now = keys.utc_now()
        last_minute = (await self.events_per_minute(1, now=now))[0]["count"]
        active = await self.active_users(minutes, now=now)
        return {
            "total_events": _as_int(await self._redis.get(keys.events_total_key())),
            "events_last_minute": last_minute,
            "events_per_second": round(last_minute / 60, 4),
            "active_users_last_window": active["unique_users"],
            "window_minutes": minutes,
            "rolling_five_minute_engagement": await self.rolling_engagement(5, now=now),
            "job_click_through_rate": (await self.job_click_through_rate(limit))["overall"]["rate"],
            "connection_requests_this_hour": await self._get_int(
                keys.connection_requests_key(keys.hour_bucket(now))
            ),
            "trending_posts": (await self.trending_posts(minutes, limit, now=now))["posts"],
            "trending_jobs": (await self.trending_jobs(minutes, limit, now=now))["jobs"],
            "events_by_device": await self.counts_by_label("devices:seen", keys.device_count_key, minutes, now),
            "events_by_source": await self.counts_by_label("sources:seen", keys.source_count_key, minutes, now),
            "duplicate_events": await self._get_int(keys.duplicates_total_key()),
            "dead_letters": await self._get_int(keys.dead_letters_total_key()),
            "retries": await self._get_int(keys.retries_total_key()),
            "consumer_lag": await self._get_int(keys.consumer_lag_key()),
        }

    async def events_per_minute(self, minutes: int = 15, now: datetime | None = None) -> list[dict]:
        moment = now or keys.utc_now()
        buckets = keys.iter_minute_buckets(moment, minutes)
        values = await self._redis.mget([keys.events_count_key(bucket) for bucket in buckets])
        return [
            {"minute": bucket, "count": _as_int(value)}
            for bucket, value in zip(reversed(buckets), reversed(values), strict=True)
        ]

    async def active_users(self, minutes: int = 5, now: datetime | None = None) -> dict:
        moment = now or keys.utc_now()
        buckets = keys.iter_minute_buckets(moment, minutes)
        redis_keys = [keys.active_users_key(bucket) for bucket in buckets]
        users = await self._redis.sunion(redis_keys) if redis_keys else set()
        per_minute = []
        for bucket, redis_key in zip(reversed(buckets), reversed(redis_keys), strict=True):
            per_minute.append({"minute": bucket, "unique_users": await self._redis.scard(redis_key)})
        return {
            "window_minutes": minutes,
            "unique_users": len(users),
            "per_minute": per_minute,
        }

    async def trending_posts(self, minutes: int = 5, limit: int = 10, now: datetime | None = None) -> dict:
        return {
            "window_minutes": minutes,
            "posts": await self._trending(keys.trending_posts_key, "post_id", minutes, limit, now),
        }

    async def trending_jobs(self, minutes: int = 5, limit: int = 10, now: datetime | None = None) -> dict:
        return {
            "window_minutes": minutes,
            "jobs": await self._trending(keys.trending_jobs_key, "job_id", minutes, limit, now),
        }

    async def job_click_through_rate(self, limit: int = 10) -> dict:
        clicks = await self._get_int(keys.job_clicks_total_key())
        views = await self._get_int(keys.job_views_total_key())
        job_ids = await self._redis.smembers("jobs:seen")
        jobs = []
        for job_id in job_ids:
            job_clicks = await self._get_int(keys.job_clicks_key(job_id))
            job_views = await self._get_int(keys.job_views_key(job_id))
            jobs.append(
                {
                    "job_id": job_id,
                    "clicks": job_clicks,
                    "views": job_views,
                    "rate": click_through_rate(job_clicks, job_views),
                }
            )
        jobs.sort(key=lambda item: (item["clicks"], item["rate"]), reverse=True)
        return {
            "overall": {
                "clicks": clicks,
                "views": views,
                "rate": click_through_rate(clicks, views),
            },
            "jobs": jobs[:limit],
        }

    async def connection_requests_per_hour(self, hours: int = 24, now: datetime | None = None) -> dict:
        moment = now or keys.utc_now()
        buckets = keys.iter_hour_buckets(moment, hours)
        values = await self._redis.mget([keys.connection_requests_key(bucket) for bucket in buckets])
        return {
            "hours": [
                {"hour": bucket, "count": _as_int(value)}
                for bucket, value in zip(reversed(buckets), reversed(values), strict=True)
            ]
        }

    async def rolling_engagement(self, minutes: int = 5, now: datetime | None = None) -> int:
        moment = now or keys.utc_now()
        buckets = keys.iter_minute_buckets(moment, minutes)
        values = await self._redis.mget([keys.engagement_key(bucket) for bucket in buckets])
        return sum(_as_int(value) for value in values)

    async def counts_by_label(
        self,
        seen_key: str,
        key_builder,
        minutes: int,
        now: datetime | None = None,
    ) -> dict[str, int]:
        moment = now or keys.utc_now()
        labels = await self._redis.smembers(seen_key)
        buckets = keys.iter_minute_buckets(moment, minutes)
        counts: dict[str, int] = {}
        for label in labels:
            values = await self._redis.mget([key_builder(label, bucket) for bucket in buckets])
            counts[label] = sum(_as_int(value) for value in values)
        return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))

    async def _trending(
        self,
        key_builder,
        id_field: str,
        minutes: int,
        limit: int,
        now: datetime | None,
    ) -> list[dict]:
        moment = now or keys.utc_now()
        windows: list[list[tuple[str, float]]] = []
        for bucket in keys.iter_minute_buckets(moment, minutes):
            rows = await self._redis.zrevrange(key_builder(bucket), 0, -1, withscores=True)
            windows.append([(member, float(score)) for member, score in rows])
        return [{id_field: member, "score": score} for member, score in merge_scores(windows, limit)]

    async def _get_int(self, key: str) -> int:
        return _as_int(await self._redis.get(key))
