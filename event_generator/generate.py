#!/usr/bin/env python3
"""Generate synthetic PulseStream activity, including occasional duplicates and invalid events."""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from uuid import uuid4

from shared.recommendations.catalog import matching_jobs

EVENT_TYPES = (
    "profile_view",
    "post_view",
    "post_like",
    "post_comment",
    "connection_request",
    "job_view",
    "job_click",
    "job_save",
    "company_follow",
)
SOURCES = ("feed", "search", "recommended_jobs", "profile", "notifications")
DEVICES = ("mobile", "desktop", "tablet")


def users(count: int) -> list[str]:
    return [f"user_{index:03d}" for index in range(1, count + 1)]


def posts(count: int) -> list[str]:
    return [f"post_{index:03d}" for index in range(1, count + 1)]


def jobs(count: int) -> list[str]:
    return [f"job_{index:03d}" for index in range(1, count + 1)]


def target_for(
    event_type: str,
    post_ids: list[str],
    job_ids: list[str],
    user_ids: list[str],
    user_id: str,
) -> str:
    if event_type.startswith("post_"):
        return random.choice(post_ids)
    if event_type.startswith("job_"):
        aligned = matching_jobs(user_id, job_ids)
        if aligned and random.random() < 0.7:
            return random.choice(aligned)
        return random.choice(job_ids)
    if event_type in {"profile_view", "connection_request"}:
        return random.choice(user_ids)
    return f"company_{random.randint(1, 20):03d}"


def build_event(user_ids: list[str], post_ids: list[str], job_ids: list[str]) -> dict:
    event_type = random.choice(EVENT_TYPES)
    user_id = random.choice(user_ids)
    return {
        "event_id": str(uuid4()),
        "user_id": user_id,
        "event_type": event_type,
        "target_id": target_for(event_type, post_ids, job_ids, user_ids, user_id),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metadata": {"source": random.choice(SOURCES), "device": random.choice(DEVICES)},
    }


def post_event(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{url}/api/v1/events",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def publish_invalid(payload: str) -> None:
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
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic PulseStream events")
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--posts", type=int, default=10)
    parser.add_argument("--jobs", type=int, default=12)
    parser.add_argument("--duplicate-rate", type=float, default=0.08)
    parser.add_argument("--invalid-rate", type=float, default=0.05)
    parser.add_argument("--ingest-url", default="http://localhost:8000")
    args = parser.parse_args()

    user_ids = users(args.users)
    post_ids = posts(args.posts)
    job_ids = jobs(args.jobs)
    sent: list[dict] = []
    accepted = 0
    duplicates = 0
    invalid = 0

    for _ in range(args.count):
        roll = random.random()
        if sent and roll < args.duplicate_rate:
            payload = random.choice(sent)
            duplicates += 1
        elif roll < args.duplicate_rate + args.invalid_rate:
            publish_invalid('{"event_id":"not-a-valid-event"}')
            invalid += 1
            continue
        else:
            payload = build_event(user_ids, post_ids, job_ids)
            sent.append(payload)
        try:
            result = post_event(args.ingest_url, payload)
        except urllib.error.URLError as exc:
            print(f"publish failed: {exc}", file=sys.stderr)
            return 1
        if result.get("status") == "accepted":
            accepted += 1

    print(
        json.dumps(
            {
                "accepted": accepted,
                "unique_payloads": len(sent),
                "duplicate_sends": duplicates,
                "invalid_sends": invalid,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
