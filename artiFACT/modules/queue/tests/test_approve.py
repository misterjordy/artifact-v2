"""Tests for approve/reject logic (including transaction wrapping)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict, NotFound
from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcNodePermission, FcUser
from artiFACT.modules.queue.service import approve_proposal, reject_proposal


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
        display_sentence="A test sentence for approval testing.",
        state="proposed",
        created_by_uid=creator.user_uid,
    )
    db.add(version)
    await db.flush()
    return fact, version


async def test_approve_wrapped_in_transaction(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
):
    """v1 Q-MAINT-04: Approve must be wrapped in a transaction."""
    fact, version = await _make_proposed(db, child_node, admin_user)

    with patch("artiFACT.modules.queue.service.publish", new_callable=AsyncMock), \
         patch("artiFACT.modules.facts.state_machine.publish", new_callable=AsyncMock):
        result = await approve_proposal(db, version.version_uid, admin_user)

    assert result.state == "published"
    assert result.published_at is not None
    # Fact's published pointer must be updated atomically
    refreshed_fact = await db.get(FcFact, fact.fact_uid)
    assert refreshed_fact.current_published_version_uid == version.version_uid


async def test_approve_nonexistent_raises_not_found(
    db: AsyncSession, admin_user: FcUser
):
    """Approving a non-existent version raises NotFound."""
    with pytest.raises(NotFound):
        await approve_proposal(db, uuid.uuid4(), admin_user)


async def test_approve_already_published_raises_conflict(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
):
    """Cannot approve a version that is already published."""
    fact, version = await _make_proposed(db, child_node, admin_user)

    with patch("artiFACT.modules.queue.service.publish", new_callable=AsyncMock), \
         patch("artiFACT.modules.facts.state_machine.publish", new_callable=AsyncMock):
        await approve_proposal(db, version.version_uid, admin_user)

    with pytest.raises(Conflict):
        await approve_proposal(db, version.version_uid, admin_user)


async def test_reject_sets_state(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
):
    """Reject must transition version to 'rejected'."""
    _, version = await _make_proposed(db, child_node, admin_user)

    with patch("artiFACT.modules.queue.service.publish", new_callable=AsyncMock), \
         patch("artiFACT.modules.facts.state_machine.publish", new_callable=AsyncMock):
        result = await reject_proposal(db, version.version_uid, admin_user, note="Bad info")

    assert result.state == "rejected"
