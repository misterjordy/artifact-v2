"""Tests for audit event recorder."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.modules.audit.recorder import get_pending_events
from artiFACT.modules.facts.service import create_fact, retire_fact


async def test_event_recorded_on_create(db: AsyncSession, admin_user, child_node):
    """Creating a fact must emit an event captured by the recorder."""
    from artiFACT.modules.audit.recorder import _pending_events

    _pending_events.clear()

    fact, version = await create_fact(
        db, child_node.node_uid, f"A recorded fact for testing audit {uuid.uuid4().hex[:8]}.", admin_user
    )

    events = get_pending_events()
    assert len(events) >= 1
    fact_event = [e for e in events if e.entity_type == "fact"]
    assert len(fact_event) >= 1
    assert fact_event[0].event_type == "fact.created"
    assert fact_event[0].actor_uid == str(admin_user.user_uid)


async def test_event_recorded_on_retire(db: AsyncSession, admin_user, child_node):
    """Retiring a fact must emit an event captured by the recorder."""
    from artiFACT.modules.audit.recorder import _pending_events

    _pending_events.clear()

    fact, _ = await create_fact(
        db, child_node.node_uid, f"A fact to retire for audit test {uuid.uuid4().hex[:8]}.", admin_user
    )
    await db.flush()

    _pending_events.clear()

    await retire_fact(db, fact.fact_uid, admin_user)

    events = get_pending_events()
    retire_events = [e for e in events if e.event_type == "fact.retired"]
    assert len(retire_events) == 1
    assert retire_events[0].entity_uid == str(fact.fact_uid)
