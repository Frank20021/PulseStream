import json
import logging

from aiokafka import AIOKafkaProducer

from shared.config import Settings
from shared.kafka.client import kafka_client_kwargs
from shared.schemas import ActivityEvent

logger = logging.getLogger(__name__)


class EventProducer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._producer = AIOKafkaProducer(
            acks="all",
            **kafka_client_kwargs(settings),
        )

    async def start(self) -> None:
        await self._producer.start()
        logger.info("kafka_producer_started")

    async def stop(self) -> None:
        await self._producer.stop()
        logger.info("kafka_producer_stopped")

    async def publish(self, event: ActivityEvent) -> None:
        await self._producer.send_and_wait(
            topic=self._settings.kafka_topic_activity,
            key=event.user_id.encode("utf-8"),
            value=event.model_dump_json().encode("utf-8"),
        )
        logger.info(
            "event_published",
            extra={
                "event_id": str(event.event_id),
                "event_type": event.event_type.value,
                "user_id": event.user_id,
            },
        )

    async def publish_dead_letter(self, message: dict, key: str | None = None) -> None:
        await self._producer.send_and_wait(
            topic=self._settings.kafka_topic_dlq,
            key=(key or "unknown").encode("utf-8"),
            value=json.dumps(message, default=str).encode("utf-8"),
        )
        logger.info(
            "event_dead_lettered",
            extra={
                "event_id": message.get("event_id"),
                "retry_count": message.get("retry_count"),
                "topic": self._settings.kafka_topic_dlq,
            },
        )
