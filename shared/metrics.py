from prometheus_client import Counter, Gauge, Histogram

EVENTS_ACCEPTED = Counter(
    "pulsestream_events_accepted_total",
    "Events accepted by the ingestion API",
)
EVENTS_PROCESSED = Counter(
    "pulsestream_events_processed_total",
    "Events handled by the consumer",
    ["outcome"],
)
RETRIES = Counter(
    "pulsestream_retries_total",
    "Transient processing retries",
)
DEAD_LETTERS = Counter(
    "pulsestream_dead_letters_total",
    "Events sent to the dead-letter topic",
)
PROCESSING_LATENCY = Histogram(
    "pulsestream_processing_latency_seconds",
    "Time to process one Kafka record",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
)
DB_WRITE_LATENCY = Histogram(
    "pulsestream_db_write_latency_seconds",
    "PostgreSQL event insert latency",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)
CONSUMER_LAG = Gauge(
    "pulsestream_consumer_lag",
    "Sum of partition lag for the event consumer",
)
