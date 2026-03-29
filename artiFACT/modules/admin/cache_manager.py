"""Redis cache operations: stats, selective flush."""

from typing import Any

import redis.asyncio as aioredis

from artiFACT.kernel.config import settings


async def get_cache_stats() -> dict[str, Any]:
    """Return Redis memory, client, and hit/miss stats."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)  # type: ignore[no-untyped-call]  # redis stub gap
    try:
        info = await r.info("memory", "clients", "stats", "keyspace")
        db_info = info.get("db0", {})
        total_keys = db_info.get("keys", 0) if isinstance(db_info, dict) else 0

        return {
            "used_memory_human": info.get("used_memory_human", "0B"),
            "connected_clients": info.get("connected_clients", 0),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
            "total_keys": total_keys,
        }
    finally:
        await r.aclose()


async def flush_all() -> int:
    """Flush all Redis keys. Returns count of flushed keys."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)  # type: ignore[no-untyped-call]  # redis stub gap
    try:
        count: int = await r.dbsize()
        await r.flushdb()
        return count
    finally:
        await r.aclose()


async def flush_by_pattern(pattern: str) -> int:
    """Flush keys matching a glob pattern (e.g. 'permissions:*')."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)  # type: ignore[no-untyped-call]  # redis stub gap
    try:
        count = 0
        async for key in r.scan_iter(match=pattern):
            await r.delete(key)
            count += 1
        return count
    finally:
        await r.aclose()
