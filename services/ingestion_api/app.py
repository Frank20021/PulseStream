import logging
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

from shared.config import get_settings
from shared.health import readiness_checks
from shared.kafka import EventProducer, ensure_topics
from shared.logging import configure_logging
from shared.metrics import EVENTS_ACCEPTED
from shared.schemas import ActivityEvent

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


class EventAccepted(BaseModel):
    event_id: UUID
    status: str = "accepted"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_topics(settings)
    producer = EventProducer(settings)
    await producer.start()
    app.state.producer = producer
    try:
        yield
    finally:
        await producer.stop()


app = FastAPI(
    title="PulseStream Ingestion API",
    version="0.6.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> JSONResponse:
    checks = await readiness_checks(settings)
    if all(value == "ok" for value in checks.values()):
        return JSONResponse({"status": "ready", "checks": checks})
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready", "checks": checks},
    )


@app.post("/api/v1/events", status_code=status.HTTP_202_ACCEPTED, response_model=EventAccepted)
async def ingest_event(event: ActivityEvent) -> EventAccepted:
    try:
        await app.state.producer.publish(event)
    except Exception:
        logger.exception("event_publish_failed", extra={"event_id": str(event.event_id)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event could not be published to Kafka",
        ) from None
    EVENTS_ACCEPTED.inc()
    return EventAccepted(event_id=event.event_id)
