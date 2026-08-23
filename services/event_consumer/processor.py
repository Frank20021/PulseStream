import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from enum import Enum

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from shared.analytics import AnalyticsWriter
from shared.config import Settings
from shared.database import Event, FailedEvent
from shared.database.session import open_session
from shared.kafka import EventProducer
from shared.metrics import DB_WRITE_LATENCY, DEAD_LETTERS, EVENTS_PROCESSED, RETRIES
from shared.redis import IdempotencyStore
from shared.retry import TransientProcessingError, backoff_seconds, is_transient
from shared.schemas import ActivityEvent

logger = logging.getLogger(__name__)


class Outcome(str, Enum):
    STORED = "stored"
    DUPLICATE = "duplicate"
    DEAD_LETTERED = "dead_lettered"


def peek_event_id(raw: str) -> str | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and data.get("event_id") is not None:
        return str(data["event_id"])
    return None


def parse_payload(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    return data if isinstance(data, dict) else {"raw": raw}


class EventProcessor:
    def __init__(
        self,
        settings: Settings,
        idempotency: IdempotencyStore,
        producer: EventProducer,
        analytics: AnalyticsWriter | None = None,
    ) -> None:
        self._settings = settings
        self._idempotency = idempotency
        self._producer = producer
        self._analytics = analytics

    async def handle_raw(self, raw: str) -> Outcome:
        event_id = peek_event_id(raw)
        try:
            event = ActivityEvent.model_validate_json(raw)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            await self._dead_letter(raw, event_id, str(exc), retry_count=0)
            EVENTS_PROCESSED.labels(outcome=Outcome.DEAD_LETTERED.value).inc()
            return Outcome.DEAD_LETTERED

        event_id = str(event.event_id)
        last_error: BaseException | None = None
        max_attempts = self._settings.max_processing_attempts

        for attempt in range(1, max_attempts + 1):
            try:
                outcome = await self._process(event)
                EVENTS_PROCESSED.labels(outcome=outcome.value).inc()
                if outcome == Outcome.DUPLICATE and self._analytics is not None:
                    await self._analytics.record_ops(duplicates=1)
                logger.info(
                    "event_processed",
                    extra={
                        "event_id": event_id,
                        "event_type": event.event_type.value,
                        "user_id": event.user_id,
                        "outcome": outcome.value,
                        "attempt": attempt,
                    },
                )
                return outcome
            except TransientProcessingError as exc:
                last_error = exc
                RETRIES.inc()
                if self._analytics is not None:
                    await self._analytics.record_ops(retries=1)
                if attempt == max_attempts:
                    break
                wait = backoff_seconds(attempt)
                logger.warning(
                    "event_retry",
                    extra={
                        "event_id": event_id,
                        "attempt": attempt,
                        "wait_seconds": wait,
                        "error": str(exc),
                    },
                )
                await asyncio.sleep(wait)

        error_message = str(last_error) if last_error else "unknown processing failure"
        await self._dead_letter(raw, event_id, error_message, retry_count=max_attempts)
        EVENTS_PROCESSED.labels(outcome=Outcome.DEAD_LETTERED.value).inc()
        return Outcome.DEAD_LETTERED

    async def _process(self, event: ActivityEvent) -> Outcome:
        event_id = str(event.event_id)
        if await self._idempotency.already_processed(event_id):
            return Outcome.DUPLICATE

        session = open_session()
        try:
            session.add(
                Event(
                    event_id=event.event_id,
                    user_id=event.user_id,
                    event_type=event.event_type.value,
                    target_id=event.target_id,
                    event_timestamp=event.timestamp,
                    processed_at=datetime.now(timezone.utc),
                    metadata_=event.metadata.model_dump(exclude_none=True),
                )
            )
            started = time.perf_counter()
            session.commit()
            DB_WRITE_LATENCY.observe(time.perf_counter() - started)
        except IntegrityError:
            session.rollback()
            await self._idempotency.mark_processed(event_id)
            return Outcome.DUPLICATE
        except Exception as exc:
            session.rollback()
            if is_transient(exc):
                raise TransientProcessingError(str(exc)) from exc
            raise
        finally:
            session.close()

        await self._idempotency.mark_processed(event_id)
        if self._analytics is not None:
            try:
                await self._analytics.record(event)
            except Exception:
                logger.warning(
                    "analytics_update_failed",
                    extra={"event_id": event_id, "outcome": Outcome.STORED.value},
                )
        return Outcome.STORED

    async def _dead_letter(
        self,
        raw: str,
        event_id: str | None,
        error_message: str,
        retry_count: int,
    ) -> None:
        failed_at = datetime.now(timezone.utc)
        payload = parse_payload(raw)
        message = {
            "event_id": event_id,
            "payload": payload,
            "error_message": error_message,
            "retry_count": retry_count,
            "failed_at": failed_at.isoformat(),
        }
        await self._producer.publish_dead_letter(message, key=event_id)
        self._store_failed_event(event_id, payload, error_message, retry_count)
        DEAD_LETTERS.inc()
        if self._analytics is not None:
            await self._analytics.record_ops(dead_letters=1)
        logger.error(
            "event_failed",
            extra={
                "event_id": event_id,
                "retry_count": retry_count,
                "error": error_message,
                "outcome": Outcome.DEAD_LETTERED.value,
            },
        )

    def _store_failed_event(
        self,
        event_id: str | None,
        payload: dict,
        error_message: str,
        retry_count: int,
    ) -> None:
        session = open_session()
        try:
            session.add(
                FailedEvent(
                    event_id=event_id,
                    payload=payload,
                    error_message=error_message,
                    retry_count=retry_count,
                )
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
