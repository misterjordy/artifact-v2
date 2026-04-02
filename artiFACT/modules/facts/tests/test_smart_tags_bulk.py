"""Tests for bulk smart tags: origin tracking, replace mode, estimation, sibling context."""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcUser
from artiFACT.modules.facts.service import create_fact, edit_fact
from artiFACT.modules.facts.smart_tags import (
    estimate_bulk_tokens,
    filter_tags,
    generate_tags_batch,
    generate_tags_single,
    sync_tags_text,
    update_tags_auto,
    update_tags_manual,
)


# ── Tag origin separation ──


async def test_manual_tags_stored_in_manual_column(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
):
    fact, ver = await create_fact(
        db, child_node.node_uid,
        f"Manual tag column test {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    accepted, _ = await update_tags_manual(db, ver.version_uid, ["fips 140-2"], admin_user)

    assert ver.smart_tags_manual == accepted
    assert ver.smart_tags == []  # auto tags untouched


async def test_auto_tags_stored_in_auto_column(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
):
    fact, ver = await create_fact(
        db, child_node.node_uid,
        f"Auto tag column test {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    ver.smart_tags_manual = ["pre-existing manual"]
    await db.flush()

    mock_resp = json.dumps({"tags": ["cloud hosting", "deployment"]})
    with patch(
        "artiFACT.modules.facts.smart_tags.AIProvider.complete",
        new_callable=AsyncMock, return_value=mock_resp,
    ):
        await generate_tags_single(db, ver.version_uid, admin_user)

    assert len(ver.smart_tags) > 0
    assert ver.smart_tags_manual == ["pre-existing manual"]


async def test_sync_tags_text_unions_both_columns(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
):
    fact, ver = await create_fact(
        db, child_node.node_uid,
        f"Sync union test {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    ver.smart_tags = ["cloud"]
    ver.smart_tags_manual = ["fips"]
    sync_tags_text(ver)
    assert ver.smart_tags_text == "cloud fips"


async def test_version_out_includes_both_tag_lists():
    from artiFACT.modules.facts.schemas import VersionOut

    fields = VersionOut.model_fields
    assert "smart_tags" in fields
    assert "smart_tags_manual" in fields


async def test_carry_forward_copies_both_columns(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
):
    fact, ver = await create_fact(
        db, child_node.node_uid,
        f"Carry forward both cols {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    ver.smart_tags = ["cloud", "hosting"]
    ver.smart_tags_manual = ["fips 140-2"]
    ver.smart_tags_text = "cloud hosting fips 140-2"
    await db.flush()

    fact, new_ver = await edit_fact(
        db, fact.fact_uid,
        f"Carry forward edited {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    assert new_ver.smart_tags == ["cloud", "hosting"]
    assert new_ver.smart_tags_manual == ["fips 140-2"]


# ── Filter improvements ──


def test_filter_replaces_underscores_with_spaces():
    result = filter_tags(
        ["defense_acquisition", "naval_drone"],
        "This is an unrelated test sentence for filtering.",
    )
    assert "defense acquisition" in result
    assert "naval drone" in result


def test_filter_cross_tag_dedup_removes_pure_subsets():
    result = filter_tags(
        [
            "procurement level",
            "major defense acquisition",
            "category one",
            "defense acquisition",
            "program management",
            "dod acquisition",
            "defense category",
        ],
        "This is a test sentence about something unrelated.",
    )
    assert "defense acquisition" not in result
    assert "defense category" not in result
    assert "dod acquisition" in result


def test_filter_cross_tag_dedup_keeps_partial_overlap():
    result = filter_tags(
        ["military procurement", "procurement level"],
        "This is a test sentence about something unrelated.",
    )
    assert "military procurement" in result
    assert "procurement level" in result


def test_filter_with_exclude_stems():
    """Exclude stems seeded from manual tags — pure subsets only."""
    result = filter_tags(
        ["fips", "cryptographic module", "encryption standard"],
        "The system meets federal security requirements.",
        exclude_stems={"fip"},
    )
    # "fips" → stems {"fip"} ⊆ exclude → SKIP
    assert "fips" not in result
    assert "cryptographic module" in result
    # "fips compliance" survives because "complianc" is a new stem
    result2 = filter_tags(
        ["fips compliance", "crypto module"],
        "The system meets federal security requirements.",
        exclude_stems={"fip"},
    )
    assert "fips compliance" in result2


# ── Nondestructive bulk ──


async def test_nondestructive_skips_already_tagged(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
):
    versions = []
    for i in range(5):
        _, v = await create_fact(
            db, child_node.node_uid,
            f"Nondestructive test fact {i} {uuid.uuid4().hex[:8]}.",
            admin_user, auto_approve=True,
        )
        versions.append(v)
    await db.flush()

    versions[0].smart_tags = ["existing"]
    versions[0].smart_tags_text = "existing"
    versions[1].smart_tags = ["also existing"]
    versions[1].smart_tags_text = "also existing"
    await db.flush()

    call_count = 0

    async def mock_complete(self, db, user_uid, messages, **kwargs):
        nonlocal call_count
        call_count += 1
        content = messages[1]["content"]
        n = len([l for l in content.split("\n") if l.strip().startswith(("1.", "2.", "3.", "4.", "5."))])
        return json.dumps({"results": [
            {"fact": j + 1, "tags": [f"gen-{j}"]} for j in range(n)
        ]})

    with patch("artiFACT.modules.facts.smart_tags.AIProvider.complete", mock_complete):
        result = await generate_tags_batch(db, child_node.node_uid, admin_user, replace=False)

    assert result["tagged_count"] == 3
    assert versions[0].smart_tags == ["existing"]
    assert versions[1].smart_tags == ["also existing"]


async def test_nondestructive_preserves_manual_tags(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
):
    _, ver = await create_fact(
        db, child_node.node_uid,
        f"Manual preserved test {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    ver.smart_tags_manual = ["fips"]
    await db.flush()

    mock_resp = json.dumps({"results": [{"fact": 1, "tags": ["cloud hosting"]}]})
    with patch(
        "artiFACT.modules.facts.smart_tags.AIProvider.complete",
        new_callable=AsyncMock, return_value=mock_resp,
    ):
        await generate_tags_batch(db, child_node.node_uid, admin_user, replace=False)

    assert ver.smart_tags_manual == ["fips"]


# ── Replace bulk ──


async def test_replace_regenerates_auto_tags(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
):
    versions = []
    for i in range(3):
        _, v = await create_fact(
            db, child_node.node_uid,
            f"Replace regen test {i} {uuid.uuid4().hex[:8]}.",
            admin_user, auto_approve=True,
        )
        v.smart_tags = [f"old-tag-{i}"]
        v.smart_tags_text = f"old-tag-{i}"
        versions.append(v)
    await db.flush()

    mock_resp = json.dumps({"results": [
        {"fact": j + 1, "tags": [f"new-tag-{j}"]} for j in range(3)
    ]})
    with patch(
        "artiFACT.modules.facts.smart_tags.AIProvider.complete",
        new_callable=AsyncMock, return_value=mock_resp,
    ):
        result = await generate_tags_batch(db, child_node.node_uid, admin_user, replace=True)

    assert result["tagged_count"] == 3
    for v in versions:
        assert "old-tag" not in " ".join(v.smart_tags)


async def test_replace_preserves_manual_tags(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
):
    _, ver = await create_fact(
        db, child_node.node_uid,
        f"Replace preserves manual {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    ver.smart_tags = ["old auto"]
    ver.smart_tags_manual = ["fips 140-2"]
    await db.flush()

    mock_resp = json.dumps({"results": [{"fact": 1, "tags": ["new auto tag"]}]})
    with patch(
        "artiFACT.modules.facts.smart_tags.AIProvider.complete",
        new_callable=AsyncMock, return_value=mock_resp,
    ):
        await generate_tags_batch(db, child_node.node_uid, admin_user, replace=True)

    assert ver.smart_tags_manual == ["fips 140-2"]
    assert "old auto" not in ver.smart_tags


# ── Token estimation ──


async def test_estimate_nondestructive_counts_untagged_only(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
):
    for i in range(5):
        _, v = await create_fact(
            db, child_node.node_uid,
            f"Estimate nondestr test {i} {uuid.uuid4().hex[:8]}.",
            admin_user, auto_approve=True,
        )
        if i < 2:
            v.smart_tags = [f"tag-{i}"]
    await db.flush()

    est = await estimate_bulk_tokens(db, child_node.node_uid, replace=False)
    assert est["fact_count"] == 3
    assert est["batch_count"] == 1


async def test_estimate_replace_counts_all(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
):
    for i in range(5):
        _, v = await create_fact(
            db, child_node.node_uid,
            f"Estimate replace test {i} {uuid.uuid4().hex[:8]}.",
            admin_user, auto_approve=True,
        )
        v.smart_tags = [f"tag-{i}"]
    await db.flush()

    est = await estimate_bulk_tokens(db, child_node.node_uid, replace=True)
    assert est["fact_count"] == 5
    assert est["batch_count"] == 1


async def test_estimate_returns_token_numbers(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
):
    _, v = await create_fact(
        db, child_node.node_uid,
        f"Estimate tokens test {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    est = await estimate_bulk_tokens(db, child_node.node_uid, replace=True)
    assert est["estimated_input_tokens"] > 0
    assert est["estimated_output_tokens"] > 0
    assert est["estimated_total_tokens"] > 0


# ── Sibling node context ──


async def test_batch_prompt_includes_sibling_node_names(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode,
):
    # Create a sibling node
    sibling = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root_node.node_uid,
        title="Sibling Category",
        slug=f"sibling-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    db.add(sibling)
    await db.flush()

    _, v = await create_fact(
        db, child_node.node_uid,
        f"Sibling context test fact {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    captured = []

    async def mock_complete(self, db, user_uid, messages, **kwargs):
        captured.extend(messages)
        return json.dumps({"results": [{"fact": 1, "tags": ["test tag"]}]})

    with patch("artiFACT.modules.facts.smart_tags.AIProvider.complete", mock_complete):
        await generate_tags_batch(db, child_node.node_uid, admin_user)

    user_msg = captured[1]["content"]
    assert "SIBLING CATEGORIES" in user_msg
    assert "Sibling Category" in user_msg


# ── Manual tag extrapolation in batch prompt ──


async def test_batch_prompt_includes_manual_tags_when_present(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
):
    _, v = await create_fact(
        db, child_node.node_uid,
        f"Manual extrapolation test {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    v.smart_tags_manual = ["fips 140-2"]
    await db.flush()

    captured = []

    async def mock_complete(self, db, user_uid, messages, **kwargs):
        captured.extend(messages)
        return json.dumps({"results": [{"fact": 1, "tags": ["crypto module"]}]})

    with patch("artiFACT.modules.facts.smart_tags.AIProvider.complete", mock_complete):
        await generate_tags_batch(db, child_node.node_uid, admin_user)

    user_msg = captured[1]["content"]
    assert "HUMAN-ASSIGNED TAGS" in user_msg
    assert "fips 140-2" in user_msg.lower()


async def test_batch_prompt_excludes_manual_section_when_none(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
):
    _, v = await create_fact(
        db, child_node.node_uid,
        f"No manual tags test {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    captured = []

    async def mock_complete(self, db, user_uid, messages, **kwargs):
        captured.extend(messages)
        return json.dumps({"results": [{"fact": 1, "tags": ["test tag"]}]})

    with patch("artiFACT.modules.facts.smart_tags.AIProvider.complete", mock_complete):
        await generate_tags_batch(db, child_node.node_uid, admin_user)

    user_msg = captured[1]["content"]
    assert "HUMAN-ASSIGNED TAGS" not in user_msg


# ── Auto tags don't overlap manual tag stems ──


async def test_auto_generation_excludes_manual_stem_overlap(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode,
):
    _, ver = await create_fact(
        db, child_node.node_uid,
        f"Manual stem overlap test {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    ver.smart_tags_manual = ["fips 140-2"]
    await db.flush()

    # "fips standard" has only stem "fip" (+ "standard" from fact) → excluded
    # "crypto module" has no overlap with manual stems → kept
    mock_resp = json.dumps({"tags": ["fips standard", "crypto module", "key management"]})
    with patch(
        "artiFACT.modules.facts.smart_tags.AIProvider.complete",
        new_callable=AsyncMock, return_value=mock_resp,
    ):
        tags = await generate_tags_single(db, ver.version_uid, admin_user)

    assert "crypto module" in tags
    assert "key management" in tags
