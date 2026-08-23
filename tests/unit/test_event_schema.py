from datetime import datetime

import pytest
from pydantic import ValidationError

from shared.schemas import ActivityEvent


VALID = {
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "user_102",
    "event_type": "job_click",
    "target_id": "job_894",
    "timestamp": "2026-08-22T14:30:00Z",
    "metadata": {"source": "recommended_jobs", "device": "mobile"},
}


def test_valid_event_parses() -> None:
    event = ActivityEvent.model_validate(VALID)
    assert event.event_type.value == "job_click"
    assert event.timestamp.tzinfo is not None


def test_unsupported_event_type_is_rejected() -> None:
    payload = {**VALID, "event_type": "stock_tick"}
    with pytest.raises(ValidationError):
        ActivityEvent.model_validate(payload)


def test_naive_timestamp_is_rejected() -> None:
    payload = {**VALID, "timestamp": datetime(2026, 8, 22, 14, 30, 0)}
    with pytest.raises(ValidationError, match="timezone"):
        ActivityEvent.model_validate(payload)


def test_missing_required_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ActivityEvent.model_validate({"event_id": VALID["event_id"]})


def test_non_uuid_event_id_is_rejected() -> None:
    payload = {**VALID, "event_id": "evt_12345"}
    with pytest.raises(ValidationError):
        ActivityEvent.model_validate(payload)
