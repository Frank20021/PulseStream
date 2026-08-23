import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx

from tests.conftest import ANALYTICS_URL, INGEST_URL

ROOT = Path(__file__).resolve().parents[1]


def new_event(
    event_type: str = "job_click",
    target_id: str = "job_894",
    user_id: str | None = None,
) -> dict:
    return {
        "event_id": str(uuid4()),
        "user_id": user_id or f"user_{uuid4().hex[:8]}",
        "event_type": event_type,
        "target_id": target_id,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metadata": {"source": "tests", "device": "desktop"},
    }


def post_event(payload: dict, timeout: float = 5.0) -> httpx.Response:
    return httpx.post(f"{INGEST_URL}/api/v1/events", json=payload, timeout=timeout)


def analytics_summary() -> dict:
    return httpx.get(f"{ANALYTICS_URL}/api/v1/analytics/summary", timeout=5.0).json()


def _psql(sql: str) -> str:
    result = compose("exec", "-T", "postgres", "psql", "-U", "pulsestream", "-d", "pulsestream", "-tAc", sql)
    return result.stdout.strip()


def event_row_count(event_id: str) -> int:
    return int(_psql(f"SELECT count(*) FROM events WHERE event_id::text = '{event_id}';") or 0)


def failed_row_count(event_id: str) -> int:
    return int(_psql(f"SELECT count(*) FROM failed_events WHERE event_id = '{event_id}';") or 0)


def total_event_rows() -> int:
    return int(_psql("SELECT count(*) FROM events;") or 0)


def hourly_metric_count() -> int:
    return int(_psql("SELECT count(*) FROM hourly_metrics;") or 0)


def redis_total_events() -> int:
    result = compose("exec", "-T", "redis", "redis-cli", "GET", "metrics:events:total")
    value = result.stdout.strip()
    if not value or value == "(nil)":
        return 0
    return int(value)


def publish_invalid_kafka(payload: str) -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "kafka",
            "/opt/kafka/bin/kafka-console-producer.sh",
            "--bootstrap-server",
            "localhost:9092",
            "--topic",
            "activity-events",
        ],
        input=payload + "\n",
        text=True,
        check=True,
        capture_output=True,
        cwd=ROOT,
    )


def compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", *args],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def celery_call(task: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "celery-worker",
            "python",
            "-c",
            f"from services.celery_worker.tasks import {task}; print({task}.delay().get(timeout=60))",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return result.stdout.strip()
