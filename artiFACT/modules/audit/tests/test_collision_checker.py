"""Tests for collision checker."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcEventLog, FcFact
from artiFACT.modules.audit.collision_checker import (
    batch_check_collisions,
    check_collision,
    check_collision_strict,
)


async def test_collision_unretire_safe(db: AsyncSession, admin_user, child_node):
    """No collision when fact is still retired."""
    fact = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=child_node.node_uid,
        created_by_uid=admin_user.user_uid,
        is_retired=True,
    )
    db.add(fact)
    await db.flush()

    event = FcEventLog(
        event_uid=uuid.uuid4(),
        entity_type="fact",
        entity_uid=str(fact.fact_uid),
        event_type="fact.retired",
        actor_uid=str(admin_user.user_uid),
        reversible=True,
        reverse_payload={"action": "unretire", "fact_uid": str(fact.fact_uid)},
    )
    db.add(event)
    await db.flush()

    reason = await check_collision(db, event)
    assert reason is None


async def test_collision_unretire_stale(db: AsyncSession, admin_user, child_node):
    """Collision when fact is no longer retired."""
    fact = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=child_node.node_uid,
        created_by_uid=admin_user.user_uid,
        is_retired=False,
    )
    db.add(fact)
    await db.flush()

    event = FcEventLog(
        event_uid=uuid.uuid4(),
        entity_type="fact",
        entity_uid=str(fact.fact_uid),
        event_type="fact.retired",
        actor_uid=str(admin_user.user_uid),
        reversible=True,
        reverse_payload={"action": "unretire", "fact_uid": str(fact.fact_uid)},
    )
    db.add(event)
    await db.flush()

    reason = await check_collision(db, event)
    assert reason is not None
    assert "state has changed" in reason


async def test_collision_strict_raises(db: AsyncSession, admin_user, child_node):
    """check_collision_strict raises Conflict on collision."""
    from artiFACT.kernel.exceptions import Conflict

    fact = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=child_node.node_uid,
        created_by_uid=admin_user.user_uid,
        is_retired=False,
    )
    db.add(fact)
    await db.flush()

    event = FcEventLog(
        event_uid=uuid.uuid4(),
        entity_type="fact",
        entity_uid=str(fact.fact_uid),
        event_type="fact.retired",
        actor_uid=str(admin_user.user_uid),
        reversible=True,
        reverse_payload={"action": "unretire", "fact_uid": str(fact.fact_uid)},
    )
    db.add(event)
    await db.flush()

    with pytest.raises(Conflict, match="state has changed"):
        await check_collision_strict(db, event)


async def test_batch_check_collisions(db: AsyncSession, admin_user, child_node):
    """Batch collision check returns results for all events."""
    fact_ok = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=child_node.node_uid,
        created_by_uid=admin_user.user_uid,
        is_retired=True,
    )
    fact_stale = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=child_node.node_uid,
        created_by_uid=admin_user.user_uid,
        is_retired=False,
    )
    db.add_all([fact_ok, fact_stale])
    await db.flush()

    event_ok = FcEventLog(
        event_uid=uuid.uuid4(),
        entity_type="fact",
        entity_uid=str(fact_ok.fact_uid),
        event_type="fact.retired",
        actor_uid=str(admin_user.user_uid),
        reversible=True,
        reverse_payload={"action": "unretire", "fact_uid": str(fact_ok.fact_uid)},
    )
    event_stale = FcEventLog(
        event_uid=uuid.uuid4(),
        entity_type="fact",
        entity_uid=str(fact_stale.fact_uid),
        event_type="fact.retired",
        actor_uid=str(admin_user.user_uid),
        reversible=True,
        reverse_payload={"action": "unretire", "fact_uid": str(fact_stale.fact_uid)},
    )
    db.add_all([event_ok, event_stale])
    await db.flush()

    results = await batch_check_collisions(db, [event_ok, event_stale])
    assert results[event_ok.event_uid] is None
    assert results[event_stale.event_uid] is not None
    assert "state has changed" in results[event_stale.event_uid]


async def test_already_undone_detected(db: AsyncSession, admin_user, child_node):
    """Batch check detects already-undone events."""
    from datetime import datetime, timezone

    fact = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=child_node.node_uid,
        created_by_uid=admin_user.user_uid,
        is_retired=True,
    )
    db.add(fact)
    await db.flush()

    event = FcEventLog(
        event_uid=uuid.uuid4(),
        entity_type="fact",
        entity_uid=str(fact.fact_uid),
        event_type="fact.retired",
        actor_uid=str(admin_user.user_uid),
        reversible=True,
        reverse_payload={"action": "unretire", "fact_uid": str(fact.fact_uid)},
        undone_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.flush()

    reason = await check_collision(db, event)
    assert reason == "Already undone"
