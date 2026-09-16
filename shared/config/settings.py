from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_security_protocol: str = "PLAINTEXT"
    kafka_sasl_mechanism: str | None = None
    kafka_sasl_username: str | None = None
    kafka_sasl_password: str | None = None
    kafka_topic_activity: str = "activity-events"
    kafka_topic_dlq: str = "activity-events-dlq"
    kafka_topic_analytics: str = "analytics-updates"
    kafka_activity_partitions: int = 4
    kafka_replication_factor: int = 1
    kafka_consumer_group: str = "pulsestream-event-consumer"

    database_url: str = "postgresql://pulsestream:pulsestream@postgres:5432/pulsestream"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"

    idempotency_ttl_seconds: int = 86400
    max_processing_attempts: int = 4

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
