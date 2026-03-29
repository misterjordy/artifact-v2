"""Tests for fact creation."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict
from artiFACT.modules.facts.service import create_fact


async def test_create_sets_created_by(db: AsyncSession, admin_user, child_node):
    """Regression test for v1 F-DATA-01: created_by_uid must always be set."""
    with patch("artiFACT.modules.facts.service.validate_duplicate", new_callable=AsyncMock):
        fact, version = await create_fact(
            db, child_node.node_uid, "This is a test fact sentence.", admin_user
        )
    assert fact.created_by_uid == admin_user.user_uid
    assert version.created_by_uid == admin_user.user_uid


async def test_contributor_creates_proposed(db: AsyncSession, contributor_user, child_node):
    """A contributor should create facts in 'proposed' state."""
    with patch("artiFACT.modules.facts.service.validate_duplicate", new_callable=AsyncMock):
        fact, version = await create_fact(
            db, child_node.node_uid, "Contributor creates proposed fact.", contributor_user
        )
    assert version.state == "proposed"
    assert version.published_at is None


async def test_approver_creates_published(db: AsyncSession, approver_user, child_node):
    """An approver should auto-publish facts they create."""
    with patch("artiFACT.modules.facts.service.validate_duplicate", new_callable=AsyncMock):
        fact, version = await create_fact(
            db, child_node.node_uid, "Approver creates published fact.", approver_user
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
