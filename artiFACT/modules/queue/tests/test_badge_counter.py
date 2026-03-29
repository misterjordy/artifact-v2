"""Tests for badge_counter — cached count, invalidation."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcUser
from artiFACT.modules.queue.badge_counter import (
    _compute_count,
    get_badge_count,
    invalidate_badge_cache,
)


async def _make_proposed(
    db: AsyncSession, node: FcNode, creator: FcUser, count: int = 1
) -> list[FcFactVersion]:
    """Create `count` proposed facts/versions in the given node."""
    versions = []
    for i in range(count):
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
            display_sentence=f"Badge test sentence number {i}.",
            state="proposed",
            created_by_uid=creator.user_uid,
        )
        db.add(version)
        await db.flush()
        versions.append(version)
    return versions


async def test_badge_count_accurate_after_approve(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
):
    """Badge count must reflect actual proposal count after an approve."""
    versions = await _make_proposed(db, child_node, admin_user, count=3)
    node_uids = [child_node.node_uid]

    count_before = await _compute_count(db, node_uids)
    assert count_before == 3

    # Simulate approving one
    versions[0].state = "published"
    await db.flush()

    count_after = await _compute_count(db, node_uids)
    assert count_after == 2


async def test_compute_count_empty_scope(db: AsyncSession):
    """Empty node list should return 0."""
    count = await _compute_count(db, [])
    assert count == 0


async def test_compute_count_excludes_retired(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
):
    """Retired facts should not count toward the badge."""
    fact = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=child_node.node_uid,
        created_by_uid=admin_user.user_uid,
        is_retired=True,
    )
    db.add(fact)
    await db.flush()

    version = FcFactVersion(
        version_uid=uuid.uuid4(),
        fact_uid=fact.fact_uid,
        display_sentence="Retired fact badge test sentence.",
        state="proposed",
        created_by_uid=admin_user.user_uid,
    )
    db.add(version)
    await db.flush()

    count = await _compute_count(db, [child_node.node_uid])
    assert count == 0
