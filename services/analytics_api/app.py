import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from shared.aggregates import (
    failed_event_count,
    list_daily_job_metrics,
    list_daily_metrics,
    list_hourly_metrics,
    list_scheduled_reports,
)
from shared.analytics import AnalyticsReader
from shared.config import get_settings
from shared.health import readiness_checks
from shared.logging import configure_logging
from shared.recommendations import ensure_catalog, list_users, recommend_jobs
from shared.redis import close_redis, get_redis

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_catalog()
    app.state.reader = AnalyticsReader(get_redis())
    try:
        yield
    finally:
        await close_redis()


app = FastAPI(
    title="PulseStream Analytics API",
    version="0.7.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


def reader() -> AnalyticsReader:
    return app.state.reader


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> JSONResponse:
    checks = await readiness_checks(settings, include_kafka=False)
    if all(value == "ok" for value in checks.values()):
        return JSONResponse({"status": "ready", "checks": checks})
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready", "checks": checks},
    )


@app.get("/api/v1/analytics/summary")
async def summary(
    minutes: int = Query(default=5, ge=1, le=60),
    limit: int = Query(default=5, ge=1, le=50),
) -> dict:
    data = await reader().summary(minutes=minutes, limit=limit)
    data["failed_events"] = failed_event_count()
    return data


@app.get("/api/v1/analytics/events-per-minute")
async def events_per_minute(minutes: int = Query(default=15, ge=1, le=60)) -> dict:
    return {"minutes": await reader().events_per_minute(minutes)}


@app.get("/api/v1/analytics/active-users")
async def active_users(minutes: int = Query(default=5, ge=1, le=60)) -> dict:
    return await reader().active_users(minutes)


@app.get("/api/v1/analytics/trending-posts")
async def trending_posts(
    minutes: int = Query(default=5, ge=1, le=60),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    return await reader().trending_posts(minutes, limit)


@app.get("/api/v1/analytics/trending-jobs")
async def trending_jobs(
    minutes: int = Query(default=5, ge=1, le=60),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    return await reader().trending_jobs(minutes, limit)


@app.get("/api/v1/analytics/job-click-through-rate")
async def job_click_through_rate(limit: int = Query(default=10, ge=1, le=50)) -> dict:
    return await reader().job_click_through_rate(limit)


@app.get("/api/v1/analytics/connection-requests")
async def connection_requests(hours: int = Query(default=24, ge=1, le=72)) -> dict:
    return await reader().connection_requests_per_hour(hours)


@app.get("/api/v1/analytics/engagement")
async def engagement(minutes: int = Query(default=5, ge=1, le=60)) -> dict:
    return {
        "window_minutes": minutes,
        "rolling_engagement": await reader().rolling_engagement(minutes),
    }


@app.get("/api/v1/analytics/hourly")
def hourly(hours: int = Query(default=24, ge=1, le=168)) -> dict:
    return {"metrics": list_hourly_metrics(hours)}


@app.get("/api/v1/analytics/daily")
def daily(days: int = Query(default=7, ge=1, le=90)) -> dict:
    return {
        "event_types": list_daily_metrics(days),
        "jobs": list_daily_job_metrics(days),
    }


@app.get("/api/v1/analytics/reports")
def reports(
    report_type: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    return {"reports": list_scheduled_reports(report_type, limit)}


@app.get("/api/v1/recommendations/users")
def recommendation_users() -> dict:
    return {"users": list_users()}


@app.get("/api/v1/recommendations/jobs")
def recommendation_jobs(
    user_id: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict:
    return recommend_jobs(user_id, limit)
