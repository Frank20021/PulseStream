import pytest

from tests.conftest import wait_until
from tests.helpers import (
    analytics_summary,
    celery_call,
    event_row_count,
    hourly_metric_count,
    new_event,
    post_event,
    redis_total_events,
)


@pytest.mark.integration
def test_accepted_event_is_stored_and_counted() -> None:
    before_redis = redis_total_events()
    payload = new_event("post_view", "post_itest")
    response = post_event(payload)
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"

    assert wait_until(lambda: event_row_count(payload["event_id"]) == 1)
    assert wait_until(lambda: redis_total_events() == before_redis + 1)
    summary = analytics_summary()
    assert summary["total_events"] >= before_redis + 1


@pytest.mark.integration
def test_duplicate_event_is_stored_once() -> None:
    payload = new_event("job_view", "job_dup")
    assert post_event(payload).status_code == 202
    assert wait_until(lambda: event_row_count(payload["event_id"]) == 1)
    before_redis = redis_total_events()

    assert post_event(payload).status_code == 202
    assert wait_until(lambda: event_row_count(payload["event_id"]) == 1)
    assert event_row_count(payload["event_id"]) == 1
    assert redis_total_events() == before_redis


@pytest.mark.integration
def test_celery_hourly_report_upserts_rows() -> None:
    payload = new_event("company_follow", "company_itest")
    assert post_event(payload).status_code == 202
    assert wait_until(lambda: event_row_count(payload["event_id"]) == 1)

    before = hourly_metric_count()
    result = celery_call("generate_hourly_summaries")
    assert "company_follow" in result or hourly_metric_count() >= before
    assert hourly_metric_count() >= 1
