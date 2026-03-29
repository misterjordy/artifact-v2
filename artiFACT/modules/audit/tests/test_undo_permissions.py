"""Tests specifically for undo permission checking."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Forbidden
from artiFACT.kernel.models import FcEventLog, FcFact
from artiFACT.modules.audit.undo_engine import undo_event


async def test_non_admin_cannot_undo_others_actions(
    db: AsyncSession, admin_user, contributor_user, child_node
):
    """Non-admin users cannot undo actions performed by others."""
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

    with pytest.raises(Forbidden, match="only undo your own"):
        await undo_event(db, event.event_uid, contributor_user)
