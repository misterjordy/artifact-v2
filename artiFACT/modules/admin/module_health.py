"""Per-module health checks: DB, Redis, S3 connectivity."""

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.config import settings
from artiFACT.kernel.s3 import get_s3_client


async def check_db(db: AsyncSession) -> bool:
    """Verify database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_redis() -> bool:
    """Verify Redis connectivity."""
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        await r.aclose()
        return True
    except Exception:
        return False


def check_s3() -> bool:
    """Verify S3/MinIO connectivity."""
    try:
        client = get_s3_client()
        client.head_bucket(Bucket=settings.S3_BUCKET)
        return True
    except Exception:
        return False


async def get_module_health(db: AsyncSession) -> list[dict]:
    """Return health status for each module's dependencies."""
    db_ok = await check_db(db)
    redis_ok = await check_redis()
    s3_ok = check_s3()

    modules = [
        "auth_admin", "taxonomy", "facts", "audit",
        "queue", "search", "signing", "ai_chat",
        "import_pipeline", "export", "admin",
    ]

    return [
        {"module": name, "db": db_ok, "redis": redis_ok, "s3": s3_ok}
        for name in modules
    ]
