"""Aggregate metrics: users, facts, queue, system."""

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcEventLog, FcFact, FcFactVersion, FcUser
from artiFACT.modules.admin.system_info import get_app_version, get_deploy_sha, get_uptime

_START_TIME = time.monotonic()


async def get_dashboard(db: AsyncSession) -> dict:
    """Return aggregate dashboard metrics."""
    now = datetime.now(timezone.utc)

    # User metrics
    total_users = (await db.execute(select(func.count(FcUser.user_uid)))).scalar() or 0
    active_24h = (
        await db.execute(
            select(func.count(FcUser.user_uid)).where(
                FcUser.last_login_at > now - timedelta(hours=24)
            )
        )
    ).scalar() or 0

    role_rows = (
        await db.execute(
            select(FcUser.global_role, func.count(FcUser.user_uid)).group_by(FcUser.global_role)
        )
    ).all()
    by_role = {row[0]: row[1] for row in role_rows}

    # Fact metrics
    total_facts = (
        await db.execute(select(func.count(FcFact.fact_uid)).where(FcFact.is_retired.is_(False)))
    ).scalar() or 0

    state_rows = (
        await db.execute(
            select(FcFactVersion.state, func.count(FcFactVersion.version_uid)).group_by(
                FcFactVersion.state
            )
        )
    ).all()
    by_state = {row[0]: row[1] for row in state_rows}

    created_7d = (
        await db.execute(
            select(func.count(FcFact.fact_uid)).where(FcFact.created_at > now - timedelta(days=7))
        )
    ).scalar() or 0

    # Queue metrics
    pending_proposals = (
        await db.execute(
            select(func.count(FcFactVersion.version_uid)).where(FcFactVersion.state == "proposed")
        )
    ).scalar() or 0

    pending_moves = (
        await db.execute(
            select(func.count(FcEventLog.event_uid)).where(FcEventLog.event_type == "move_proposed")
        )
    ).scalar() or 0

    # Error rate (events with 'error' in type in last 24h vs total events)
    total_events_24h = (
        await db.execute(
            select(func.count(FcEventLog.event_uid)).where(
                FcEventLog.occurred_at > now - timedelta(hours=24)
            )
        )
    ).scalar() or 0

    error_events_24h = (
        await db.execute(
            select(func.count(FcEventLog.event_uid)).where(
                FcEventLog.occurred_at > now - timedelta(hours=24),
                FcEventLog.event_type.like("%error%"),
            )
        )
    ).scalar() or 0

    error_rate = (error_events_24h / total_events_24h * 100) if total_events_24h > 0 else 0.0

    return {
        "users": {
            "total": total_users,
            "active_24h": active_24h,
            "by_role": by_role,
        },
        "facts": {
            "total": total_facts,
            "by_state": by_state,
            "created_7d": created_7d,
        },
        "queue": {
            "pending_proposals": pending_proposals,
            "pending_moves": pending_moves,
        },
        "system": {
            "version": get_app_version(),
            "deploy_sha": get_deploy_sha(),
            "uptime": get_uptime(),
            "error_rate": round(error_rate, 2),
        },
    }
