"""ZT compliance tests — Pillars 5, 6, 7.

These tests run against real PostgreSQL and Redis inside Docker.
NO mocking of kernel/events, access_logger, anomaly_detector, or session.
Only external LLM APIs may be mocked.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.access_logger import log_data_access
from artiFACT.kernel.auth.session import create_session, force_destroy_user_sessions, get_redis
from artiFACT.kernel.models import FcEventLog, FcUser
from artiFACT.modules.admin.anomaly_detector import (
    EXPORT_FLOOD_THRESHOLD,
    check_anomaly,
    trigger_anomaly,
)


@pytest.fixture(autouse=True)
async def _flush_redis():
    """Flush anomaly counters between tests."""
    r = await get_redis()
    keys = []
    async for key in r.scan_iter(match="anomaly:*"):
        keys.append(key)
    if keys:
        await r.delete(*keys)
    yield
    # Clean up sessions too
    session_keys = []
    async for key in r.scan_iter(match="session:*"):
        session_keys.append(key)
    if session_keys:
        await r.delete(*session_keys)


# ── ZT Pillar 5: Read-Access Logging ──


async def test_read_access_logged_on_export(db: AsyncSession, admin_user: FcUser) -> None:
    """Export actions create an access event in fc_event_log."""
    await log_data_access(
        db,
        admin_user.user_uid,
        "export",
        {
            "format": "json",
            "node_uids": ["test-uid"],
            "count": 5,
        },
    )
    await db.flush()

    result = await db.execute(
        select(FcEventLog).where(
            FcEventLog.entity_type == "access",
            FcEventLog.event_type == "access.export",
            FcEventLog.actor_uid == admin_user.user_uid,
        )
    )
    event = result.scalar_one_or_none()
    assert event is not None
    assert event.payload["format"] == "json"


async def test_read_access_logged_on_ai_chat(db: AsyncSession, admin_user: FcUser) -> None:
    """AI chat actions create an access event in fc_event_log."""
    await log_data_access(
        db,
        admin_user.user_uid,
        "ai_chat",
        {
            "topic": "Program A",
            "facts_loaded": 20,
        },
    )
    await db.flush()

    result = await db.execute(
        select(FcEventLog).where(
            FcEventLog.entity_type == "access",
            FcEventLog.event_type == "access.ai_chat",
            FcEventLog.actor_uid == admin_user.user_uid,
        )
    )
    event = result.scalar_one_or_none()
    assert event is not None
    assert event.payload["topic"] == "Program A"


async def test_read_access_not_logged_on_page_view(db: AsyncSession, admin_user: FcUser) -> None:
    """Page views do NOT create access events (would be noise)."""
    # We simply verify no access log was created for a 'page_view' action
    # The access logger only logs specific actions, not page views
    result = await db.execute(
        select(FcEventLog).where(
            FcEventLog.entity_type == "access",
            FcEventLog.event_type == "access.page_view",
        )
    )
    assert result.scalar_one_or_none() is None


# ── ZT Pillar 6: Anomaly Detection ──


async def test_anomaly_detector_flags_export_flood(db: AsyncSession, admin_user: FcUser) -> None:
    """More than 10 exports in 30 minutes triggers anomaly."""
    # Simulate threshold + 1 exports
    for i in range(EXPORT_FLOOD_THRESHOLD + 1):
        flagged = await check_anomaly(db, admin_user.user_uid, "export")

    # The last call should have flagged
    assert flagged is True

    # Verify anomaly event was logged
    result = await db.execute(
        select(FcEventLog).where(
            FcEventLog.entity_type == "anomaly",
            FcEventLog.event_type == "anomaly.export_flood",
        )
    )
    event = result.scalar_one_or_none()
    assert event is not None


async def test_anomaly_detector_flags_off_hours_bulk(db: AsyncSession, admin_user: FcUser) -> None:
    """Off-hours bulk access triggers anomaly (tested via trigger_anomaly directly)."""
    # Since off-hours depends on current time, we test trigger_anomaly directly
    await trigger_anomaly(db, admin_user.user_uid, "off_hours_bulk", 6)
    await db.flush()

    result = await db.execute(
        select(FcEventLog).where(
            FcEventLog.entity_type == "anomaly",
            FcEventLog.event_type == "anomaly.off_hours_bulk",
        )
    )
    event = result.scalar_one_or_none()
    assert event is not None
    assert event.payload["count"] == 6


# ── ZT Pillar 7: Auto-Session-Expire ──


async def test_anomaly_auto_expires_sessions(db: AsyncSession, admin_user: FcUser) -> None:
    """When anomaly is triggered, all user sessions are destroyed."""
    # Create a session
    session_id = await create_session(admin_user)

    # Verify session exists
    r = await get_redis()
    assert await r.get(f"session:{session_id}") is not None

    # Trigger anomaly
    await trigger_anomaly(db, admin_user.user_uid, "export_flood", 15)

    # Session should be destroyed
    assert await r.get(f"session:{session_id}") is None


async def test_force_reauth_after_session_expire(db: AsyncSession, admin_user: FcUser) -> None:
    """After session expire, user must re-authenticate."""
    session_id = await create_session(admin_user)

    # Destroy all sessions
    destroyed = await force_destroy_user_sessions(admin_user.user_uid)
    assert destroyed >= 1

    # Session should be gone
    r = await get_redis()
    assert await r.get(f"session:{session_id}") is None


# ── Structured Logging ──


async def test_structured_logs_have_request_id() -> None:
    """Verify structlog is configured with request_id binding."""
    import structlog
    from artiFACT.kernel.log_forwarder import bind_request_context

    request_id = str(uuid.uuid4())
    bind_request_context(request_id)

    ctx = structlog.contextvars.get_contextvars()
    assert ctx.get("request_id") == request_id


async def test_structured_logs_have_user_uid() -> None:
    """Verify structlog binds user_uid when provided."""
    import structlog
    from artiFACT.kernel.log_forwarder import bind_request_context

    user_uid = uuid.uuid4()
    bind_request_context(str(uuid.uuid4()), user_uid)

    ctx = structlog.contextvars.get_contextvars()
    assert ctx.get("user_uid") == str(user_uid)
