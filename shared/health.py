from aiokafka.admin import AIOKafkaAdminClient
from sqlalchemy import text

from shared.config import Settings
from shared.database.session import get_engine
from shared.redis import get_redis


async def check_kafka(settings: Settings) -> str:
    admin = AIOKafkaAdminClient(bootstrap_servers=settings.kafka_bootstrap_servers)
    try:
        await admin.start()
        await admin.list_topics()
        return "ok"
    except Exception as exc:
        return f"error: {exc}"
    finally:
        await admin.close()


def check_postgres() -> str:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        return f"error: {exc}"


async def check_redis() -> str:
    try:
        await get_redis().ping()
        return "ok"
    except Exception as exc:
        return f"error: {exc}"


async def readiness_checks(settings: Settings, *, include_kafka: bool = True) -> dict[str, str]:
    checks = {
        "postgres": check_postgres(),
        "redis": await check_redis(),
    }
    if include_kafka:
        checks["kafka"] = await check_kafka(settings)
    return checks
