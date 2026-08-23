CREATE TABLE IF NOT EXISTS failed_events (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(100),
    payload JSONB NOT NULL,
    error_message TEXT NOT NULL,
    retry_count INTEGER NOT NULL,
    failed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_failed_events_event_id ON failed_events (event_id);
CREATE INDEX IF NOT EXISTS idx_failed_events_failed_at ON failed_events (failed_at);
