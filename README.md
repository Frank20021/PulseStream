# PulseStream

Real-time professional activity analytics, in the same shape as the plumbing behind a LinkedIn feed, jobs surface, or notifications: events come in continuously, they must not be lost or counted twice, and the numbers on the screen have to move as the stream moves.

Kafka carries the live event stream. Celery does scheduled work. Redis holds rolling windows. PostgreSQL is the source of truth. Pytest and Locust check that split under load and failure.

## Quick start

Python 3.12, Docker, and Make. System `python3` on macOS is often 3.9 and will fail on `str | None`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

make up
make ready
make generate
make urls
```

Then open:

- Dashboard: [http://localhost:3000](http://localhost:3000)
- Grafana: [http://localhost:3001](http://localhost:3001) (`admin` / `admin`, anonymous Viewer also works)
- Ingestion API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

The dashboard polls analytics every three seconds. `make generate` (or `make load`) gives it something to show.

## Ports

| Port | Service |
| --- | --- |
| `8000` | Ingestion API (`POST /api/v1/events`) |
| `8001` | Analytics API |
| `8002` | Consumer Prometheus metrics |
| `3000` | React dashboard |
| `3001` | Grafana |
| `9090` | Prometheus |
| `5432` | PostgreSQL |
| `6379` | Redis |
| `9092` / `9094` | Kafka (in-network / host) |

If host PostgreSQL is already bound to `5432`, Compose Postgres will not start. The app database is the container; a local `psycopg2` connection to `localhost` is a different server and will not have the `pulsestream` role.

## How an event travels

```
Client → FastAPI :8000 → Kafka activity-events (key = user_id)
                              → consumer
                                    ├── PostgreSQL `events`
                                    └── Redis rolling counters (first store only)
Analytics API :8001  ← Redis + hourly/daily tables + job recommendations
Dashboard :3000      ← Analytics API
Celery Beat/worker   → hourly/daily summaries, cleanup, Redis recompute
Prometheus/Grafana   ← /metrics on the APIs and consumer
```

A longer diagram is in [`architecture.md`](architecture.md).

**Kafka vs Celery:** Kafka handles the continuous stream (profile views, likes, job clicks, connection requests). Celery handles the clock (hourly engagement, daily job-click reports, idempotency cleanup, aggregate recompute).

`POST /api/v1/events` returns **202 accepted**, not processed. The API publishes and returns. The consumer does the durable work.

## Job recommendations

Not a neural net. For a user, each remaining job gets:

```
score = 0.50 * skill_similarity + 0.30 * interaction_similarity + 0.20 * popularity_score
```

- **Skill:** Jaccard overlap of the user's skills and the job's skills
- **Interaction:** jobs the user clicked or saved, plus collaborative filtering from similar users (overlapping click/save sets)
- **Popularity:** network-wide views, clicks, and saves

Clicked and saved jobs are excluded. Catalog users/jobs live in PostgreSQL (`users`, `jobs`) and in `shared/recommendations/catalog.py`.

```bash
make recommend
curl -sS "http://localhost:8001/api/v1/recommendations/jobs?user_id=user_001"
```

The dashboard user picker at [http://localhost:3000](http://localhost:3000) shows the same ranking, including the three component scores.

## Event shape

`event_id` is a UUID and the PostgreSQL primary key. Values such as `evt_12345` are rejected.

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user_102",
  "event_type": "job_click",
  "target_id": "job_894",
  "timestamp": "2026-08-22T14:30:00Z",
  "metadata": {"source": "recommended_jobs", "device": "mobile"}
}
```

Supported `event_type` values:

`profile_view`, `post_view`, `post_like`, `post_comment`, `connection_request`, `job_view`, `job_click`, `job_save`, `company_follow`

## Reliability

The interesting failure is: consumer writes PostgreSQL, then crashes before the Kafka offset commit. Kafka redelivers. Without guards, that event becomes two rows and two analytics increments.

Guards in this repo:

- Unique `event_id` (UUID) as the PostgreSQL primary key
- Redis `processed:event:{id}` with a 24-hour TTL
- Redis analytics counters increment only on first store

Transient errors retry at 1s, 2s, then 4s. After that the payload goes to `activity-events-dlq` and `failed_events`. Invalid JSON takes the dead-letter path immediately.

If Redis is empty, `make recompute` rebuilds counters from `events`. PostgreSQL remains authoritative.

## Tests and measured numbers

```bash
make test-unit
make test-integration
make test-failure
make load
```

**30 tests passed** on this stack.

| Suite | Count | What it covers |
| --- | --- | --- |
| Unit | 22 | Schema, unsupported types, retry 1s/2s/4s, job CTR, recommendation scoring |
| Integration | 3 | FastAPI → Kafka → PostgreSQL → Redis; duplicate `event_id`; Celery hourly upsert |
| Failure | 5 | Dead-letter for bad JSON, no double-count, consumer restart, PostgreSQL outage, Redis outage |

Locust, 25 users, 20 seconds, local Docker (22 August 2026):

| Metric | Value |
| --- | --- |
| Accepted `POST /api/v1/events` | 9,830 |
| Failures | 0 |
| Accepted events / sec | **555** |
| API P50 / P95 / P99 | **3 ms / 12 ms / 24 ms** |

The consumer kept up: PostgreSQL held 9,891 rows after the run. Full notes: [`load_tests/BENCHMARK.md`](load_tests/BENCHMARK.md). Those are laptop numbers, not a production cluster. P95 is **ingestion API** latency, not an end-to-end Kafka-to-dashboard figure.

## Interview

Use this explanation:

> I built PulseStream, a real-time activity-processing platform inspired by professional-network applications. FastAPI accepts events such as profile views, post interactions and job clicks, then publishes them to Kafka. Idempotent consumers store the events in PostgreSQL and update rolling analytics in Redis. Celery handles scheduled aggregation and cleanup. I focused heavily on reliability by adding retries, dead-letter handling, duplicate prevention, failure-injection tests and operational monitoring.

Then the technical challenge:

> The hardest issue was preventing an event from being counted twice when a consumer failed after writing to PostgreSQL but before committing its Kafka offset. I used unique event IDs, database constraints and idempotent processing so a redelivered event would not create another record or update the analytics twice.

## Resume

**PulseStream — Real-Time Activity Analytics Platform** | Python, FastAPI, Kafka, PostgreSQL, Redis, Celery, Docker

- Built a Kafka-based event-processing platform ingesting profile, feed and job interactions at **555 events/sec** with **12-ms P95** ingestion latency (9,830 requests, 0 failures on a 20-second Locust run).
- Implemented idempotent consumers, database constraints, exponential retries and dead-letter recovery, preventing duplicate processing across **5 failure-injection tests**.
- Developed Redis-backed rolling analytics, Celery aggregation jobs, and a weighted job recommender (skills, clicks/saves, similar users); monitored throughput, latency and consumer lag with Prometheus and Grafana.

## Commands

| Command | What it does |
| --- | --- |
| `make up` | Build and start the stack |
| `make urls` | Print dashboard, Grafana, API, and metrics URLs |
| `make ready` | Ingestion and analytics readiness |
| `make generate` | Synthetic users, posts, jobs, duplicates, invalid events |
| `make recommend` | Job recommendations for `user_001` |
| `make load` | 20-second Locust run against ingestion |
| `make test-unit` | Schema, retry, and CTR tests |
| `make test-integration` | Live pipeline, duplicates, Celery hourly job |
| `make test-failure` | DLQ, restart, Postgres/Redis outage |
| `make hourly-report` | Run the hourly Celery job now |
| `make recompute` | Rebuild Redis counters from PostgreSQL |
| `make down` | Stop the stack |
