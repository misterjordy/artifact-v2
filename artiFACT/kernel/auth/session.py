"""Session create/validate/destroy (Redis-backed)."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.config import settings
from artiFACT.kernel.models import FcUser

SESSION_TTL = 8 * 60 * 60  # 8 hours
REVALIDATION_WINDOW = 15 * 60  # 15 minutes

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)  # type: ignore[no-untyped-call]  # redis.asyncio stub gap
    return _redis


def _session_key(session_id: str) -> str:
    return f"session:{session_id}"


async def create_session(user: FcUser) -> str:
    """Generate UUID session, store in Redis with TTL 8hr, return session ID."""
    r = await get_redis()
    session_id = str(uuid.uuid4())
    data = {
        "user_uid": str(user.user_uid),
        "cac_dn": user.cac_dn,
        "last_validated_at": datetime.now(timezone.utc).isoformat(),
        "auto_approve": False,
    }
    await r.setex(_session_key(session_id), SESSION_TTL, json.dumps(data))
    return session_id


async def validate_session(session_id: str, db: AsyncSession) -> FcUser | None:
    """Redis lookup, return User or None. Re-check user every 15 min (ZT continuous auth)."""
    r = await get_redis()
    raw = await r.get(_session_key(session_id))
    if not raw:
        return None

    data = json.loads(raw)
    user_uid = uuid.UUID(data["user_uid"])
    last_validated = datetime.fromisoformat(data["last_validated_at"])
    now = datetime.now(timezone.utc)

    if (now - last_validated).total_seconds() > REVALIDATION_WINDOW:
        result = await db.execute(select(FcUser).where(FcUser.user_uid == user_uid))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            await destroy_session(session_id)
            return None
        data["last_validated_at"] = now.isoformat()
        ttl = await r.ttl(_session_key(session_id))
        if ttl > 0:
            await r.setex(_session_key(session_id), ttl, json.dumps(data))
        return user
    else:
        result = await db.execute(select(FcUser).where(FcUser.user_uid == user_uid))
        return result.scalar_one_or_none()


async def destroy_session(session_id: str) -> None:
    """Redis delete session."""
    r = await get_redis()
    await r.delete(_session_key(session_id))


async def get_session_data(session_id: str) -> dict[str, Any] | None:
    """Return raw session dict from Redis, or None."""
    r = await get_redis()
    raw = await r.get(_session_key(session_id))
    if not raw:
        return None
    return json.loads(raw)


async def update_session_field(session_id: str, field: str, value: Any) -> bool:
    """Update a single field in the session data. Returns True on success."""
    r = await get_redis()
    raw = await r.get(_session_key(session_id))
    if not raw:
        return False
    data = json.loads(raw)
    data[field] = value
    ttl = await r.ttl(_session_key(session_id))
    if ttl > 0:
        await r.setex(_session_key(session_id), ttl, json.dumps(data))
    return True


def is_auto_approve_active(session_data: dict[str, Any] | None) -> bool:
    """Check if auto-approve is toggled ON in session data.

    Returns False if session_data is None or field is missing
    (backward compat with old sessions).
    """
    if not session_data:
        return False
    return bool(session_data.get("auto_approve", False))


async def force_destroy_user_sessions(user_uid: uuid.UUID) -> int:
    """Scan Redis for all sessions matching this user_uid, delete all."""
    r = await get_redis()
    destroyed = 0
    async for key in r.scan_iter(match="session:*"):
        raw = await r.get(key)
        if raw:
            data = json.loads(raw)
            if data.get("user_uid") == str(user_uid):
                await r.delete(key)
                destroyed += 1
    return destroyed
