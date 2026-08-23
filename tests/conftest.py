import os
import time

import pytest

INGEST_URL = os.getenv("PULSESTREAM_INGEST_URL", "http://localhost:8000")
ANALYTICS_URL = os.getenv("PULSESTREAM_ANALYTICS_URL", "http://localhost:8001")
DATABASE_URL = os.getenv(
    "PULSESTREAM_DATABASE_URL",
    "postgresql://pulsestream:pulsestream@127.0.0.1:5432/pulsestream",
)
REDIS_URL = os.getenv("PULSESTREAM_REDIS_URL", "redis://127.0.0.1:6379/0")


def wait_until(predicate, timeout: float = 15.0, interval: float = 0.4) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


@pytest.fixture(scope="session")
def ingest_url() -> str:
    return INGEST_URL


@pytest.fixture(scope="session")
def analytics_url() -> str:
    return ANALYTICS_URL
