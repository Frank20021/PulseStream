import random
from datetime import datetime, timezone
from uuid import uuid4

from locust import HttpUser, between, task

EVENT_TYPES = (
    "profile_view",
    "post_view",
    "post_like",
    "job_view",
    "job_click",
    "connection_request",
)


class IngestionUser(HttpUser):
    wait_time = between(0.01, 0.05)

    @task(4)
    def post_event(self) -> None:
        event_type = random.choice(EVENT_TYPES)
        payload = {
            "event_id": str(uuid4()),
            "user_id": f"user_{uuid4().hex[:8]}",
            "event_type": event_type,
            "target_id": f"target_{uuid4().hex[:6]}",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "metadata": {"source": "load_test", "device": "mobile"},
        }
        with self.client.post("/api/v1/events", json=payload, catch_response=True) as response:
            if response.status_code == 202:
                response.success()
            else:
                response.failure(f"expected 202, got {response.status_code}")

    @task(1)
    def health(self) -> None:
        self.client.get("/health")
