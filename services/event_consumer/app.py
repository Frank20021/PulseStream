import asyncio
import logging
import signal
import time

from aiokafka import AIOKafkaConsumer, TopicPartition
from aiokafka.structs import OffsetAndMetadata
from prometheus_client import start_http_server

from services.event_consumer.processor import EventProcessor
from shared.analytics import AnalyticsWriter
from shared.analytics.keys import consumer_lag_key
from shared.config import get_settings
from shared.database.session import get_engine, init_db
from shared.kafka import EventProducer, ensure_topics
from shared.logging import configure_logging
from shared.metrics import CONSUMER_LAG, PROCESSING_LATENCY
from shared.redis import IdempotencyStore, close_redis, get_redis

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


async def _publish_lag(consumer: AIOKafkaConsumer, redis) -> None:
    assignment = consumer.assignment()
    if not assignment:
        return
    total = 0
    end_offsets = await consumer.end_offsets(list(assignment))
    for tp in assignment:
        high = end_offsets.get(tp)
        try:
            position = await consumer.position(tp)
        except Exception:
            continue
        if high is None or position is None:
            continue
        total += max(high - position, 0)
    CONSUMER_LAG.set(total)
    try:
        await redis.set(consumer_lag_key(), total)
    except Exception:
        logger.warning("consumer_lag_update_failed")


async def consume() -> None:
    init_db()
    start_http_server(8002)
    await ensure_topics(settings)

    producer = EventProducer(settings)
    await producer.start()
    redis = get_redis()
    processor = EventProcessor(
        settings,
        IdempotencyStore(redis, settings.idempotency_ttl_seconds),
        producer,
        AnalyticsWriter(redis),
    )

    consumer = AIOKafkaConsumer(
        settings.kafka_topic_activity,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        key_deserializer=lambda key: key.decode("utf-8") if key else None,
        value_deserializer=lambda value: value.decode("utf-8"),
    )
    await consumer.start()
    logger.info("consumer_started", extra={"topic": settings.kafka_topic_activity})

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _request_shutdown, stop)

    try:
        while not stop.is_set():
            batches = await consumer.getmany(timeout_ms=1000, max_records=10)
            for messages in batches.values():
                for message in messages:
                    started = time.perf_counter()
                    await processor.handle_raw(message.value)
                    PROCESSING_LATENCY.observe(time.perf_counter() - started)
                    await consumer.commit(
                        {
                            TopicPartition(message.topic, message.partition): OffsetAndMetadata(
                                message.offset + 1, ""
                            )
                        }
                    )
                    if stop.is_set():
                        logger.info("shutdown_after_current_record")
                        return
            await _publish_lag(consumer, redis)
    finally:
        await consumer.stop()
        await producer.stop()
        await close_redis()
        get_engine().dispose()
        logger.info("consumer_stopped")


def _request_shutdown(stop: asyncio.Event) -> None:
    logger.info("shutdown_signal_received")
    stop.set()


def main() -> None:
    asyncio.run(consume())


if __name__ == "__main__":
    main()
