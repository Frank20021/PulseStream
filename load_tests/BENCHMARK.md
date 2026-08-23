# PulseStream benchmark

Measured on 22 August 2026 against the local Docker Compose stack (FastAPI, Kafka, one consumer, PostgreSQL, Redis). These are laptop numbers, not a production cluster.

## Test command

```bash
locust -f load_tests/locustfile.py --headless -u 25 -r 10 -t 20s --host http://localhost:8000
```

25 Locust users, 10 spawned per second, 20 second run.

## Ingestion API

| Metric | Value |
| --- | --- |
| `POST /api/v1/events` requests | 9,830 |
| Failures | 0 |
| Accepted events per second | 555 |
| Average latency | 3 ms |
| Median (P50) | 3 ms |
| P95 | 12 ms |
| P99 | 24 ms |
| Max | 48 ms |

`GET /health` added 2,561 requests at about 145/s. Combined throughput was about 700 requests/s.

## Consumer and storage

After the run, PostgreSQL held 9,891 event rows. About 9,867 of those arrived in the surrounding 90 seconds, so the single consumer kept up with the 555 accepted events/s on this machine.

`processed_at - received_at` is not a useful end-to-end figure yet: both timestamps are set at insert time, so they do not measure Kafka lag.

Dead-letter rows after generator + tests: 6 (malformed payloads only).

## Automated tests

```
24 passed
```

| Suite | What it covers |
| --- | --- |
| Unit (16) | Event validation, unsupported types, retry backoff 1/2/4, click-through rate |
| Integration (3) | Accept → Kafka → PostgreSQL → Redis; duplicate `event_id`; Celery hourly upsert |
| Failure (5) | Dead-letter for invalid JSON, duplicate suppression, consumer restart, PostgreSQL outage, Redis outage |

## How to reproduce

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
make up
make test
make load
```
