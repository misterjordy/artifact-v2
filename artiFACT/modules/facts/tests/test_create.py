"""Tests for fact creation."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict
from artiFACT.modules.facts.service import create_fact


async def test_create_sets_created_by(db: AsyncSession, admin_user, child_node):
    """Regression test for v1 F-DATA-01: created_by_uid must always be set."""
    fact, version = await create_fact(
        db, child_node.node_uid, f"Test fact created_by check {uuid.uuid4().hex[:8]}.", admin_user
    )
    assert fact.created_by_uid == admin_user.user_uid
    assert version.created_by_uid == admin_user.user_uid


async def test_contributor_creates_proposed(db: AsyncSession, contributor_user, child_node):
    """A contributor should create facts in 'proposed' state."""
    fact, version = await create_fact(
        db, child_node.node_uid, f"Contributor creates proposed fact {uuid.uuid4().hex[:8]}.", contributor_user
    )
    assert version.state == "proposed"
    assert version.published_at is None


async def test_approver_creates_proposed_by_default(db: AsyncSession, approver_user, child_node):
    """An approver without auto_approve creates facts as proposed (default OFF)."""
    fact, version = await create_fact(
        db, child_node.node_uid, f"Approver creates proposed fact {uuid.uuid4().hex[:8]}.", approver_user
    )
    assert version.state == "proposed"
    assert version.published_at is None


async def test_approver_creates_published_with_auto_approve(
    db: AsyncSession, approver_user, child_node,
):
    """An approver with auto_approve=True auto-publishes facts they create."""
    fact, version = await create_fact(
        db, child_node.node_uid,
        f"Approver creates published fact {uuid.uuid4().hex[:8]}.", approver_user,
        auto_approve=True,
    )
    assert version.state == "published"
    assert version.published_at is not None
    assert fact.current_published_version_uid == version.version_uid


async def test_duplicate_rejected(db: AsyncSession, admin_user, child_node):
    """Near-duplicate facts in the same node should be rejected."""
    sentence = "This is a unique test fact sentence for duplicates."
    await create_fact(db, child_node.node_uid, sentence, admin_user)
    await db.flush()

    with pytest.raises(Conflict, match="similar fact"):
        await create_fact(db, child_node.node_uid, sentence, admin_user)


async def test_profanity_rejected(db: AsyncSession, admin_user, child_node):
    """Facts containing profanity should be rejected."""
    with pytest.raises(Conflict, match="inappropriate"):
        await create_fact(
            db, child_node.node_uid, "This is a fuck test sentence here.", admin_user
        )
