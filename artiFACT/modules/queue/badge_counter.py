"""Queue badge count for nav — Redis-cached with 60s TTL."""

import uuid

import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.session import get_redis
from artiFACT.kernel.events import subscribe
from artiFACT.kernel.models import FcFact, FcFactVersion

BADGE_TTL = 60  # 60 seconds


def _badge_key(user_uid: uuid.UUID) -> str:
    return f"badge:{user_uid}"


async def get_badge_count(
    db: AsyncSession, user_uid: uuid.UUID, node_uids: list[uuid.UUID]
) -> int:
    """Return cached proposal count, or compute and cache it."""
    r = await get_redis()
    cached = await r.get(_badge_key(user_uid))
    if cached is not None:
        return int(cached)

    count = await _compute_count(db, node_uids)
    await r.setex(_badge_key(user_uid), BADGE_TTL, str(count))
    return count


async def _compute_count(db: AsyncSession, node_uids: list[uuid.UUID]) -> int:
    """Count proposed versions in scope."""
    if not node_uids:
        return 0

    stmt = (
        select(func.count(FcFactVersion.version_uid))
        .join(FcFact, FcFactVersion.fact_uid == FcFact.fact_uid)
        .where(
            FcFactVersion.state == "proposed",
            FcFact.node_uid.in_(node_uids),
            FcFact.is_retired.is_(False),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one()


async def invalidate_badge_cache(payload: dict) -> None:
    """Event handler: flush badge cache for the acting user."""
    actor_uid = payload.get("actor_uid")
    if not actor_uid:
        return
    r = await get_redis()
    await r.delete(_badge_key(uuid.UUID(actor_uid)))


def register_badge_subscribers() -> None:
    """Subscribe to events that should invalidate the badge cache."""
    subscribe("version.approved", invalidate_badge_cache)
    subscribe("version.rejected", invalidate_badge_cache)
    subscribe("version.published", invalidate_badge_cache)
