.PHONY: up down logs logs-ops urls send-event send-new-event send-invalid seed-analytics analytics recommend ready db-events db-failed db-hourly db-daily db-reports hourly-report daily-report failure-report cleanup-keys recompute psql rebuild test-unit test-integration test-failure test generate load

up:
	docker compose up --build -d

down:
	docker compose down

rebuild:
	docker compose up --build -d --force-recreate

logs:
	docker compose logs -f ingestion-api event-consumer analytics-api celery-worker celery-beat

logs-ops:
	docker compose logs -f dashboard prometheus grafana

urls:
	@printf '%s\n' \
		'Ingestion API      http://localhost:8000/docs' \
		'Analytics API      http://localhost:8001/docs' \
		'Dashboard          http://localhost:3000' \
		'Grafana            http://localhost:3001  (admin / admin)' \
		'Prometheus         http://localhost:9090' \
		'Consumer metrics   http://localhost:8002/'

ready:
	curl -sS http://localhost:8000/ready
	@echo
	curl -sS http://localhost:8001/ready
	@echo

send-event:
	curl -sS -X POST http://localhost:8000/api/v1/events \
		-H "Content-Type: application/json" \
		-d '{"event_id":"550e8400-e29b-41d4-a716-446655440000","user_id":"user_102","event_type":"job_click","target_id":"job_894","timestamp":"2026-08-22T14:30:00Z","metadata":{"source":"recommended_jobs","device":"mobile"}}'
	@echo

send-new-event:
	curl -sS -X POST http://localhost:8000/api/v1/events \
		-H "Content-Type: application/json" \
		-d "{\"event_id\":\"$$(uuidgen | tr '[:upper:]' '[:lower:]')\",\"user_id\":\"user_102\",\"event_type\":\"job_click\",\"target_id\":\"job_894\",\"timestamp\":\"2026-08-22T14:30:00Z\",\"metadata\":{\"source\":\"recommended_jobs\",\"device\":\"mobile\"}}"
	@echo

send-invalid:
	printf '%s\n' '{"event_id":"not-a-valid-event"}' | \
		docker compose exec -T kafka /opt/kafka/bin/kafka-console-producer.sh \
		--bootstrap-server localhost:9092 --topic activity-events

seed-analytics:
	python3 scripts/seed_events.py

analytics:
	curl -sS http://localhost:8001/api/v1/analytics/summary
	@echo

recommend:
	curl -sS "http://localhost:8001/api/v1/recommendations/jobs?user_id=user_001"
	@echo

hourly-report:
	docker compose exec celery-worker python -c "from services.celery_worker.tasks import generate_hourly_summaries; print(generate_hourly_summaries.delay().get(timeout=60))"

daily-report:
	docker compose exec celery-worker python -c "from services.celery_worker.tasks import generate_daily_summaries; print(generate_daily_summaries.delay().get(timeout=60))"

failure-report:
	docker compose exec celery-worker python -c "from services.celery_worker.tasks import failure_report; print(failure_report.delay().get(timeout=60))"

cleanup-keys:
	docker compose exec celery-worker python -c "from services.celery_worker.tasks import cleanup_expired_keys; print(cleanup_expired_keys.delay().get(timeout=60))"

recompute:
	docker compose exec celery-worker python -c "from services.celery_worker.tasks import recompute_aggregates; print(recompute_aggregates.delay().get(timeout=60))"

db-events:
	docker compose exec postgres psql -U pulsestream -d pulsestream -c "SELECT event_id, user_id, event_type, target_id, processed_at FROM events;"

db-failed:
	docker compose exec postgres psql -U pulsestream -d pulsestream -c "SELECT id, event_id, error_message, retry_count, failed_at FROM failed_events;"

db-hourly:
	docker compose exec postgres psql -U pulsestream -d pulsestream -c "SELECT metric_hour, event_type, event_count, unique_users FROM hourly_metrics ORDER BY metric_hour, event_type;"

db-daily:
	docker compose exec postgres psql -U pulsestream -d pulsestream -c "SELECT metric_day, event_type, event_count, unique_users FROM daily_metrics ORDER BY metric_day, event_type;"

db-reports:
	docker compose exec postgres psql -U pulsestream -d pulsestream -c "SELECT id, report_type, period_start, created_at FROM scheduled_reports ORDER BY id;"

psql:
	docker compose exec postgres psql -U pulsestream -d pulsestream

PY ?= .venv/bin/python

test-unit:
	$(PY) -m pytest tests/unit -q

test-integration:
	$(PY) -m pytest tests/integration -q

test-failure:
	$(PY) -m pytest tests/failure -q

test: test-unit test-integration

generate:
	$(PY) -m event_generator.generate --count 40

load:
	$(PY) -m locust -f load_tests/locustfile.py --headless -u 25 -r 10 -t 20s --host http://localhost:8000 --csv load_tests/results
