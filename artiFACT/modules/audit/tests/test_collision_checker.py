"""Tests for collision checker."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict
from artiFACT.kernel.models import FcEventLog, FcFact
from artiFACT.modules.audit.collision_checker import check_collision


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

    await check_collision(db, event)


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

    with pytest.raises(Conflict, match="state has changed"):
        await check_collision(db, event)
