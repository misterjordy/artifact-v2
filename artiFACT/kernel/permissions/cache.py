"""Permission cache read/write/invalidate (Redis-backed)."""

import uuid


from artiFACT.kernel.auth.session import get_redis

PERMISSION_TTL = 300  # 5 minutes


def _perm_key(user_uid: uuid.UUID, node_uid: uuid.UUID) -> str:
    return f"perm:{user_uid}:{node_uid}"


async def get_cached_role(user_uid: uuid.UUID, node_uid: uuid.UUID) -> str | None:
    """Read cached permission role from Redis."""
    r = await get_redis()
    val = await r.get(_perm_key(user_uid, node_uid))
    return val


async def set_cached_role(user_uid: uuid.UUID, node_uid: uuid.UUID, role: str) -> None:
    """Cache resolved role in Redis with TTL."""
    r = await get_redis()
    await r.setex(_perm_key(user_uid, node_uid), PERMISSION_TTL, role)


async def invalidate_user_permissions(user_uid: uuid.UUID) -> None:
    """Flush all cached permissions for a user."""
    r = await get_redis()
    async for key in r.scan_iter(match=f"perm:{user_uid}:*"):
        await r.delete(key)
