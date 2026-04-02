"""Tests for bulk smart tags: empirical token estimation + descendant traversal."""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.ai_provider import AIUsage
from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcUser
from artiFACT.modules.facts.service import create_fact
from artiFACT.modules.facts.smart_tags import (
    estimate_bulk_tokens,
    generate_tags_batch_stream,

    get_descendant_node_uids,
    _load_published_versions,
)



async def _consume_batch_stream(db, node_uid, actor, **kwargs):
    """Test helper: consume the async generator, return final summary."""
    final = {"tagged_count": 0, "skipped_count": 0, "results": {}}
    async for evt in generate_tags_batch_stream(db, node_uid, actor, **kwargs):
        if evt.get("done"):
            final["tagged_count"] = evt.get("tagged_count", 0)
            final["skipped_count"] = evt.get("skipped_count", 0)
        elif evt.get("results"):
            final["results"].update(evt["results"])
    return final


# ── Token estimation (empirically calibrated) ──


def test_estimate_8_facts_matches_empirical():
    est = estimate_bulk_tokens(8)
    assert est["batch_count"] == 1
    assert est["estimated_input_tokens"] == 380  # 300 + 8*10
    assert est["estimated_output_tokens"] == 424  # 8*53
    assert est["estimated_total_tokens"] == 804


def test_estimate_3_facts_matches_empirical():
    est = estimate_bulk_tokens(3)
    assert est["batch_count"] == 1
    assert est["estimated_input_tokens"] == 330  # 300 + 3*10
    assert est["estimated_output_tokens"] == 159  # 3*53
    assert est["estimated_total_tokens"] == 489


def test_estimate_27_facts_multiple_batches():
    est = estimate_bulk_tokens(27)
    assert est["batch_count"] == 4  # ceil(27/8)
    assert est["estimated_input_tokens"] == 4 * 300 + 27 * 10  # 1470
    assert est["estimated_output_tokens"] == 27 * 53  # 1431
    assert est["estimated_total_tokens"] == 1470 + 1431  # 2901


def test_estimate_0_facts_returns_zeros():
    est = estimate_bulk_tokens(0)
    assert est["fact_count"] == 0
    assert est["batch_count"] == 0
    assert est["estimated_input_tokens"] == 0
    assert est["estimated_output_tokens"] == 0
    assert est["estimated_total_tokens"] == 0


# ── Descendant traversal ──


async def test_get_descendant_node_uids_includes_self(
    db: AsyncSession, root_node: FcNode,
):
    uids = await get_descendant_node_uids(db, root_node.node_uid)
    assert root_node.node_uid in uids


async def test_get_descendant_node_uids_recursive(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode,
):
    """3-level hierarchy: root → parent → child."""
    parent = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root_node.node_uid,
        title="Mid Level",
        slug=f"mid-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    child = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=parent.node_uid,
        title="Leaf Level",
        slug=f"leaf-{uuid.uuid4().hex[:8]}",
        node_depth=2,
        created_by_uid=admin_user.user_uid,
    )
    db.add_all([parent, child])
    await db.flush()

    uids = await get_descendant_node_uids(db, root_node.node_uid)
    assert root_node.node_uid in uids
    assert parent.node_uid in uids
    assert child.node_uid in uids


async def test_estimate_includes_descendant_facts(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode,
):
    """Parent node estimate should count facts in child nodes."""
    child1 = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root_node.node_uid,
        title="Child One",
        slug=f"c1-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    child2 = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root_node.node_uid,
        title="Child Two",
        slug=f"c2-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    db.add_all([child1, child2])
    await db.flush()

    for i in range(5):
        await create_fact(
            db, child1.node_uid,
            f"Child1 fact {i} descendant test {uuid.uuid4().hex[:8]}.",
            admin_user, auto_approve=True,
        )
    for i in range(5):
        await create_fact(
            db, child2.node_uid,
            f"Child2 fact {i} descendant test {uuid.uuid4().hex[:8]}.",
            admin_user, auto_approve=True,
        )
    await db.flush()

    versions = await _load_published_versions(
        db, root_node.node_uid, include_descendants=True,
    )
    assert len(versions) == 10


async def test_generate_batch_processes_descendants(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode,
):
    """generate_tags_batch on parent processes all descendant facts."""
    child1 = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root_node.node_uid,
        title="System Purpose",
        slug=f"sp-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    child2 = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root_node.node_uid,
        title="Stakeholders",
        slug=f"sh-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    db.add_all([child1, child2])
    await db.flush()

    for i in range(3):
        await create_fact(
            db, child1.node_uid,
            f"Purpose fact {i} batch desc test {uuid.uuid4().hex[:8]}.",
            admin_user, auto_approve=True,
        )
    for i in range(2):
        await create_fact(
            db, child2.node_uid,
            f"Stakeholder fact {i} batch desc test {uuid.uuid4().hex[:8]}.",
            admin_user, auto_approve=True,
        )
    await db.flush()

    call_count = 0

    async def mock_complete(self, db, user_uid, messages, **kwargs):
        nonlocal call_count
        call_count += 1
        content = messages[1]["content"]
        lines = [l for l in content.split("\n") if l.strip() and l.strip()[0].isdigit()]
        return (json.dumps({"results": [
            {"fact": j + 1, "tags": [f"tag-{call_count}-{j}"]} for j in range(len(lines))
        ]}), AIUsage())

    with patch("artiFACT.modules.facts.smart_tags.AIProvider.complete", mock_complete):
        result = await _consume_batch_stream(db, root_node.node_uid, admin_user)

    assert result["tagged_count"] == 5
    assert call_count >= 2  # at least one call per child node


async def test_generate_batch_uses_child_node_context(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode,
):
    """Each child node's batch prompt should use the child's title, not the parent's."""
    child1 = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root_node.node_uid,
        title="Unique Child Alpha",
        slug=f"uca-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    child2 = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root_node.node_uid,
        title="Unique Child Beta",
        slug=f"ucb-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    db.add_all([child1, child2])
    await db.flush()

    await create_fact(
        db, child1.node_uid,
        f"Alpha fact {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await create_fact(
        db, child2.node_uid,
        f"Beta fact {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    captured_prompts: list[str] = []

    async def mock_complete(self, db, user_uid, messages, **kwargs):
        captured_prompts.append(messages[1]["content"])
        return (json.dumps({"results": [{"fact": 1, "tags": ["test"]}]}), AIUsage())

    with patch("artiFACT.modules.facts.smart_tags.AIProvider.complete", mock_complete):
        await _consume_batch_stream(db, root_node.node_uid, admin_user)

    # Should have called AI at least twice — once per child
    assert len(captured_prompts) >= 2
    # One prompt should mention Alpha, another Beta — neither should mention the root
    all_text = " ".join(captured_prompts)
    assert "Unique Child Alpha" in all_text
    assert "Unique Child Beta" in all_text


async def test_generate_batch_empty_parent_returns_zero(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode,
):
    """Parent with no facts anywhere returns zero with no AI calls."""
    call_count = 0

    async def mock_complete(self, db, user_uid, messages, **kwargs):
        nonlocal call_count
        call_count += 1
        return (json.dumps({"results": []}), AIUsage())

    with patch("artiFACT.modules.facts.smart_tags.AIProvider.complete", mock_complete):
        result = await _consume_batch_stream(db, root_node.node_uid, admin_user)

    assert result["tagged_count"] == 0
    assert call_count == 0


async def test_fill_gaps_vs_replace_different_counts(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode,
):
    """Fill Gaps and Replace should return different fact counts."""
    for i in range(10):
        _, v = await create_fact(
            db, child_node.node_uid,
            f"Fill vs replace test {i} {uuid.uuid4().hex[:8]}.",
            admin_user, auto_approve=True,
        )
        if i < 7:
            v.smart_tags = [f"existing-{i}"]
    await db.flush()

    fill_versions = await _load_published_versions(
        db, root_node.node_uid, untagged_only=True, include_descendants=True,
    )
    replace_versions = await _load_published_versions(
        db, root_node.node_uid, untagged_only=False, include_descendants=True,
    )

    assert len(fill_versions) == 3
    assert len(replace_versions) == 10
