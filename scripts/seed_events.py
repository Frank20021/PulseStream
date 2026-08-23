#!/usr/bin/env python3
"""Publish a small mix of unique events so Redis analytics have something to show."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from uuid import uuid4

INGEST_URL = "http://localhost:8000/api/v1/events"

EVENTS = [
    ("user_101", "post_view", "post_101", "feed", "mobile"),
    ("user_102", "post_view", "post_101", "feed", "mobile"),
    ("user_103", "post_view", "post_202", "search", "desktop"),
    ("user_101", "post_like", "post_101", "feed", "mobile"),
    ("user_104", "post_comment", "post_101", "feed", "mobile"),
    ("user_102", "job_view", "job_894", "recommended_jobs", "mobile"),
    ("user_102", "job_view", "job_894", "recommended_jobs", "mobile"),
    ("user_102", "job_click", "job_894", "recommended_jobs", "mobile"),
    ("user_105", "job_view", "job_100", "search", "desktop"),
    ("user_105", "job_click", "job_100", "search", "desktop"),
    ("user_106", "job_save", "job_894", "recommended_jobs", "mobile"),
    ("user_107", "connection_request", "user_200", "profile", "desktop"),
    ("user_108", "profile_view", "user_200", "search", "mobile"),
]


def post(event: dict) -> dict:
    request = urllib.request.Request(
        INGEST_URL,
        data=json.dumps(event).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    accepted = 0
    for user_id, event_type, target_id, source, device in EVENTS:
        payload = {
            "event_id": str(uuid4()),
            "user_id": user_id,
            "event_type": event_type,
            "target_id": target_id,
            "timestamp": now,
            "metadata": {"source": source, "device": device},
        }
        try:
            result = post(payload)
        except urllib.error.URLError as exc:
            print(f"failed to publish {event_type}: {exc}", file=sys.stderr)
            return 1
        print(f"{result['status']} {event_type} {target_id} {result['event_id']}")
        accepted += 1
    print(f"accepted {accepted} events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
