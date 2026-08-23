import logging

from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError

from shared.config import Settings

logger = logging.getLogger(__name__)


async def ensure_topics(settings: Settings) -> None:
    admin = AIOKafkaAdminClient(bootstrap_servers=settings.kafka_bootstrap_servers)
    await admin.start()
    try:
        desired = [
            NewTopic(
                name=settings.kafka_topic_activity,
                num_partitions=settings.kafka_activity_partitions,
                replication_factor=1,
            ),
            NewTopic(
                name=settings.kafka_topic_dlq,
                num_partitions=1,
                replication_factor=1,
            ),
            NewTopic(
                name=settings.kafka_topic_analytics,
                num_partitions=1,
                replication_factor=1,
            ),
        ]
        existing = set(await admin.list_topics())
        topics = [topic for topic in desired if topic.name not in existing]
        if not topics:
            logger.info("Kafka topics already exist")
            return
        try:
            await admin.create_topics(topics)
            logger.info("Created Kafka topics: %s", ", ".join(t.name for t in topics))
        except TopicAlreadyExistsError:
            logger.info("Kafka topics already exist")
    finally:
        await admin.close()
