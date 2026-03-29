"""Tests for revision.py — atomic reject + create revised + publish."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict, Forbidden
from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcNodePermission, FcUser
from artiFACT.modules.queue.revision import revise_and_publish


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
        display_sentence="Original proposed sentence for revision.",
        state="proposed",
        created_by_uid=creator.user_uid,
        metadata_tags=["tag1"],
        classification="UNCLASSIFIED",
    )
    db.add(version)
    await db.flush()
    return fact, version


async def test_revision_atomic_reject_plus_publish(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
):
    """Revise language: original rejected, new version created and published atomically."""
    fact, original = await _make_proposed(db, child_node, admin_user)
    revised_text = "Revised sentence with corrected language here."

    with patch("artiFACT.modules.queue.revision.publish", new_callable=AsyncMock), \
         patch("artiFACT.modules.facts.state_machine.publish", new_callable=AsyncMock):
        revised = await revise_and_publish(
            db, original.version_uid, revised_text, admin_user, note="Fixed wording"
        )

    # Original is rejected
    refreshed_original = await db.get(FcFactVersion, original.version_uid)
    assert refreshed_original.state == "rejected"

    # Revised is published
    assert revised.state == "published"
    assert revised.display_sentence == revised_text
    assert revised.published_at is not None
    assert revised.supersedes_version_uid == original.version_uid

    # Fact points to the new version
    refreshed_fact = await db.get(FcFact, fact.fact_uid)
    assert refreshed_fact.current_published_version_uid == revised.version_uid


async def test_revision_copies_metadata(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
):
    """Revision should inherit metadata_tags and classification from original."""
    _, original = await _make_proposed(db, child_node, admin_user)

    with patch("artiFACT.modules.queue.revision.publish", new_callable=AsyncMock), \
         patch("artiFACT.modules.facts.state_machine.publish", new_callable=AsyncMock):
        revised = await revise_and_publish(
            db, original.version_uid, "Revised sentence with new text here.", admin_user
        )

    assert revised.metadata_tags == original.metadata_tags
    assert revised.classification == original.classification


async def test_revision_outside_scope_forbidden(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode, second_node: FcNode
):
    """Cannot revise a fact outside your approval scope."""
    subapprover = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=SubRev {uuid.uuid4().hex[:8]}",
        display_name="SubRev",
        global_role="viewer",
    )
    db.add(subapprover)
    await db.flush()

    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=subapprover.user_uid,
        node_uid=child_node.node_uid,
        role="subapprover",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()

    # Fact is in second_node (outside scope)
    _, version = await _make_proposed(db, second_node, admin_user)

    with pytest.raises(Forbidden, match="outside your approval scope"):
        await revise_and_publish(
            db, version.version_uid, "Attempt to revise outside scope.", subapprover
        )
