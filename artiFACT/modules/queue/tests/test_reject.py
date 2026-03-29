"""Tests for reject logic."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict, NotFound
from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcUser
from artiFACT.modules.queue.service import reject_proposal


async def _make_proposed(
    db: AsyncSession, node: FcNode, creator: FcUser
) -> tuple[FcFact, FcFactVersion]:
    fact = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=node.node_uid,
        created_by_uid=creator.user_uid,
    )
    db.add(fact)
    await db.flush()

    version = FcFactVersion(
        version_uid=uuid.uuid4(),
        fact_uid=fact.fact_uid,
        display_sentence="Test reject sentence for testing.",
        state="proposed",
        created_by_uid=creator.user_uid,
    )
    db.add(version)
    await db.flush()
    return fact, version


async def test_reject_nonexistent_raises_not_found(
    db: AsyncSession, admin_user: FcUser
):
    """Rejecting a non-existent version raises NotFound."""
    with pytest.raises(NotFound):
        await reject_proposal(db, uuid.uuid4(), admin_user)


async def test_reject_non_proposed_raises_conflict(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
):
    """Cannot reject a version that is not in 'proposed' state."""
    fact = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=child_node.node_uid,
        created_by_uid=admin_user.user_uid,
    )
    db.add(fact)
    await db.flush()

    version = FcFactVersion(
        version_uid=uuid.uuid4(),
        fact_uid=fact.fact_uid,
        display_sentence="Already published version sentence.",
        state="published",
        created_by_uid=admin_user.user_uid,
    )
    db.add(version)
    await db.flush()

    with pytest.raises(Conflict, match="Not a pending proposal"):
        await reject_proposal(db, version.version_uid, admin_user)


async def test_reject_with_note(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
):
    """Reject with a note should set version state to rejected."""
    _, version = await _make_proposed(db, child_node, admin_user)

    with patch("artiFACT.modules.queue.service.publish", new_callable=AsyncMock), \
         patch("artiFACT.modules.facts.state_machine.publish", new_callable=AsyncMock):
        result = await reject_proposal(
            db, version.version_uid, admin_user, note="Incorrect data"
        )

    assert result.state == "rejected"
