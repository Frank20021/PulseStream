import time
from uuid import uuid4

import pytest

from tests.conftest import wait_until
from tests.helpers import (
    compose,
    event_row_count,
    failed_row_count,
    new_event,
    post_event,
    publish_invalid_kafka,
    redis_total_events,
)


@pytest.mark.failure
def test_malformed_event_enters_dead_letter() -> None:
    event_id = f"bad-{uuid4().hex[:8]}"
    publish_invalid_kafka(f'{{"event_id":"{event_id}"}}')
    assert wait_until(lambda: failed_row_count(event_id) == 1, timeout=20)
    assert event_row_count(event_id) == 0


@pytest.mark.failure
def test_duplicate_delivery_does_not_double_count() -> None:
    payload = new_event("job_click", "job_fail_dup")
    assert post_event(payload).status_code == 202
    assert wait_until(lambda: event_row_count(payload["event_id"]) == 1)
    redis_before = redis_total_events()

    for _ in range(3):
        assert post_event(payload).status_code == 202
    time.sleep(2)

    assert event_row_count(payload["event_id"]) == 1
    assert redis_total_events() == redis_before


@pytest.mark.failure
def test_consumer_recovers_after_restart() -> None:
    compose("restart", "event-consumer")
    time.sleep(3)
    payload = new_event("profile_view", "user_restart")
    assert post_event(payload).status_code == 202
    assert wait_until(lambda: event_row_count(payload["event_id"]) == 1, timeout=25)


@pytest.mark.failure
def test_postgres_outage_does_not_lose_accepted_event() -> None:
    payload = new_event("job_save", "job_pg_outage")
    compose("stop", "postgres")
    try:
        response = post_event(payload)
        assert response.status_code == 202
    finally:
        compose("start", "postgres")
        time.sleep(4)
    assert wait_until(lambda: event_row_count(payload["event_id"]) == 1, timeout=30)


@pytest.mark.failure
def test_redis_outage_still_persists_event() -> None:
    payload = new_event("post_like", "post_redis_outage")
    compose("stop", "redis")
    try:
        response = post_event(payload)
        assert response.status_code == 202
        assert wait_until(lambda: event_row_count(payload["event_id"]) == 1, timeout=25)
    finally:
        compose("start", "redis")
        time.sleep(3)
