"""ZT Pillar 6+7 — Anomaly detection and auto-session-expire."""

import json
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.session import force_destroy_user_sessions, get_redis
from artiFACT.kernel.models import FcEventLog

logger = structlog.get_logger()

# Thresholds (configurable via fc_system_config in future)
EXPORT_FLOOD_THRESHOLD = 10
EXPORT_FLOOD_WINDOW = 1800  # 30 min
AI_MINING_THRESHOLD = 50
AI_MINING_WINDOW = 3600  # 1 hr
SCOPE_ESCALATION_THRESHOLD = 10
SCOPE_ESCALATION_WINDOW = 600  # 10 min
OFF_HOURS_THRESHOLD = 5
OFF_HOURS_START = 0
OFF_HOURS_END = 5


async def check_anomaly(
    db: AsyncSession,
    user_uid: uuid.UUID,
    action: str,
) -> bool:
    """Run after every data-access event. Uses Redis counters. Returns True if anomaly flagged."""
    r = await get_redis()

    if action == "export":
        return await _check_rule(
            r, db, user_uid, "export", EXPORT_FLOOD_THRESHOLD, EXPORT_FLOOD_WINDOW, "export_flood"
        )
    if action == "ai_chat":
        return await _check_rule(
            r, db, user_uid, "ai", AI_MINING_THRESHOLD, AI_MINING_WINDOW, "ai_mining"
        )
    if action == "denied":
        return await _check_rule(
            r,
            db,
            user_uid,
            "deny",
            SCOPE_ESCALATION_THRESHOLD,
            SCOPE_ESCALATION_WINDOW,
            "scope_escalation",
        )
    return False


async def check_off_hours(
    db: AsyncSession,
    user_uid: uuid.UUID,
) -> bool:
    """Rule 3: Off-hours bulk access check."""
    now = datetime.now(timezone.utc)
    if OFF_HOURS_START <= now.hour < OFF_HOURS_END:
        r = await get_redis()
        return await _check_rule(
            r, db, user_uid, "offhours", OFF_HOURS_THRESHOLD, 3600, "off_hours_bulk"
        )
    return False


async def _check_rule(
    r: aioredis.Redis,
    db: AsyncSession,
    user_uid: uuid.UUID,
    counter_name: str,
    threshold: int,
    window: int,
    rule_name: str,
) -> bool:
    """Increment a Redis counter and trigger anomaly if threshold exceeded."""
    key = f"anomaly:{counter_name}:{user_uid}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, window)
    if count > threshold:
        await trigger_anomaly(db, user_uid, rule_name, count)
        return True
    return False


async def trigger_anomaly(
    db: AsyncSession,
    user_uid: uuid.UUID,
    rule: str,
    count: int,
) -> None:
    """Log anomaly, destroy sessions, alert admins."""
    # 1. Log the anomaly event
    event = FcEventLog(
        entity_type="anomaly",
        entity_uid=user_uid,
        event_type=f"anomaly.{rule}",
        payload={"count": count, "triggered_at": datetime.now(timezone.utc).isoformat()},
        actor_uid=user_uid,
    )
    db.add(event)
    await db.flush()

    # 2. Auto-expire all sessions (force re-CAC)
    destroyed = await force_destroy_user_sessions(user_uid)
    logger.warning(
        "anomaly_triggered",
        user_uid=str(user_uid),
        rule=rule,
        count=count,
        sessions_destroyed=destroyed,
    )

    # 3. Alert admin via Redis pub/sub
    r = await get_redis()
    await r.publish(
        "admin:alerts",
        json.dumps(
            {
                "user_uid": str(user_uid),
                "rule": rule,
                "count": count,
                "time": datetime.now(timezone.utc).isoformat(),
            }
        ),
    )
