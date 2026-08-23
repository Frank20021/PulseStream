CREATE TABLE IF NOT EXISTS hourly_metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_hour TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_count BIGINT NOT NULL,
    unique_users BIGINT NOT NULL,
    UNIQUE (metric_hour, event_type)
);

CREATE TABLE IF NOT EXISTS daily_metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_day TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_count BIGINT NOT NULL,
    unique_users BIGINT NOT NULL,
    UNIQUE (metric_day, event_type)
);

CREATE TABLE IF NOT EXISTS daily_job_metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_day TIMESTAMPTZ NOT NULL,
    job_id VARCHAR(100) NOT NULL,
    views BIGINT NOT NULL,
    clicks BIGINT NOT NULL,
    saves BIGINT NOT NULL,
    UNIQUE (metric_day, job_id)
);

CREATE TABLE IF NOT EXISTS scheduled_reports (
    id BIGSERIAL PRIMARY KEY,
    report_type VARCHAR(50) NOT NULL,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scheduled_reports_type ON scheduled_reports (report_type);
