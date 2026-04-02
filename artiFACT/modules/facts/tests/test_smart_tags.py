"""Tests for smart tag generation, validation, and management."""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcAiUsage, FcFact, FcFactVersion, FcUser
from artiFACT.modules.facts.service import create_fact, edit_fact
from artiFACT.modules.facts.smart_tags import (
    filter_tags,
    generate_tags_batch,
    generate_tags_single,
    get_fact_stems,
    stem_word,
    sync_tags_text,
    update_tags_manual,
    validate_tag,
)


# ── Stem validation ──


def test_stem_word_basic():
    assert stem_word("versioning") == "version"
    assert stem_word("hosting") == "host"


def test_get_fact_stems_skips_short_tokens():
    stems = get_fact_stems("An AI system is deployed")
    assert "an" not in stems
    assert "is" not in stems
    assert "ai" not in stems
    assert "system" in stems


def test_validate_tag_rejects_exact_word_from_fact():
    fact = "FastAPI is the web framework"
    assert validate_tag("fastapi", fact) is False
    assert validate_tag("framework", fact) is False


def test_validate_tag_accepts_related_but_not_duplicate():
    fact = "FastAPI is the web framework"
    assert validate_tag("REST API", fact) is True
    assert validate_tag("Python backend", fact) is True


def test_validate_tag_stemmed_not_exact():
    fact = "Each fact is version-controlled and signable"
    assert validate_tag("versioning", fact) is False
    assert validate_tag("version history", fact) is True


def test_validate_tag_multi_word_partial_overlap_accepted():
    fact = "Redis serves as the Celery message broker"
    assert validate_tag("Redis caching", fact) is True
    assert validate_tag("message queue", fact) is True


def test_filter_tags_caps_at_twelve():
    tags = [f"tag{i}" for i in range(15)]
    result = filter_tags(tags, "Some unrelated fact sentence here for testing.")
    assert len(result) == 12


def test_filter_tags_deduplicates():
    result = filter_tags(
        ["hosting", "Hosting", "HOSTING"],
        "The system uses cloud deployment.",
    )
    assert result == ["hosting"]


def test_filter_tags_strips_whitespace():
    result = filter_tags(
        ["  hosting  ", "deployment "],
        "The system uses cloud infrastructure.",
    )
    assert result == ["hosting", "deployment"]


def test_filter_tags_cross_tag_stem_dedup():
    """Tags whose stems are all already covered by earlier tags get pruned."""
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
    assert "procurement level" in result
    assert "major defense acquisition" in result
    assert "category one" in result
    assert "defense acquisition" not in result  # {defens, acquisit} both seen
    assert "program management" in result
    assert "dod acquisition" in result  # "dod" is new
    assert "defense category" not in result  # {defens, categori} both seen


# ── sync_tags_text ──


async def test_sync_tags_text(db: AsyncSession, admin_user: FcUser, child_node):
    fact, version = await create_fact(
        db, child_node.node_uid,
        f"Test sync tags text {uuid.uuid4().hex[:8]}.", admin_user,
    )
    version.smart_tags = ["cloud", "hosting", "GovCloud"]
    sync_tags_text(version)
    assert version.smart_tags_text == "cloud hosting GovCloud"


# ── Generation (single) ──


async def test_generate_single_calls_ai_and_stores_tags(
    db: AsyncSession, admin_user: FcUser, child_node,
):
    fact, version = await create_fact(
        db, child_node.node_uid,
        f"COSMOS hosts all services in GovCloud {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    mock_response = json.dumps({
        "tags": ["cloud infrastructure", "hosting", "IL-4", "FedRAMP", "AWS"]
    })

    with patch(
        "artiFACT.modules.facts.smart_tags.AIProvider.complete",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        tags = await generate_tags_single(db, version.version_uid, admin_user)

    assert len(tags) > 0
    assert version.smart_tags == tags
    assert version.smart_tags_text == " ".join(tags)

    result = await db.execute(
        select(FcAiUsage).where(FcAiUsage.action == "smart_tags")
    )
    assert result.scalar_one_or_none() is not None


async def test_generate_single_includes_siblings_in_prompt(
    db: AsyncSession, admin_user: FcUser, child_node,
):
    siblings = []
    for i in range(3):
        _, v = await create_fact(
            db, child_node.node_uid,
            f"Sibling fact number {i} about testing {uuid.uuid4().hex[:8]}.",
            admin_user, auto_approve=True,
        )
        siblings.append(v)
    await db.flush()

    target_fact, target_version = await create_fact(
        db, child_node.node_uid,
        f"Target fact for sibling test {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    captured_messages = []

    async def capture_complete(self, db, user_uid, messages, **kwargs):
        captured_messages.extend(messages)
        return json.dumps({"tags": ["testing", "validation"]})

    with patch(
        "artiFACT.modules.facts.smart_tags.AIProvider.complete",
        capture_complete,
    ):
        await generate_tags_single(db, target_version.version_uid, admin_user)

    user_msg = captured_messages[1]["content"]
    assert "SIBLING FACTS" in user_msg
    assert "Sibling fact number" in user_msg


async def test_generate_single_filters_duplicates_from_ai_output(
    db: AsyncSession, admin_user: FcUser, child_node,
):
    fact, version = await create_fact(
        db, child_node.node_uid,
        f"PostgreSQL database stores all records {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    mock_response = json.dumps({
        "tags": ["postgresql", "database", "relational", "backup", "storage"]
    })

    with patch(
        "artiFACT.modules.facts.smart_tags.AIProvider.complete",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        tags = await generate_tags_single(db, version.version_uid, admin_user)

    assert "postgresql" not in tags
    assert "database" not in tags
    assert "relational" in tags
    assert "backup" in tags


# ── Generation (batch) ──


async def test_generate_batch_skips_already_tagged(
    db: AsyncSession, admin_user: FcUser, child_node,
):
    versions = []
    for i in range(5):
        _, v = await create_fact(
            db, child_node.node_uid,
            f"Batch test fact {i} content {uuid.uuid4().hex[:8]}.",
            admin_user, auto_approve=True,
        )
        versions.append(v)
    await db.flush()

    versions[0].smart_tags = ["existing-tag"]
    versions[0].smart_tags_text = "existing-tag"
    versions[1].smart_tags = ["another-tag"]
    versions[1].smart_tags_text = "another-tag"
    await db.flush()

    call_count = 0

    async def mock_complete(self, db, user_uid, messages, **kwargs):
        nonlocal call_count
        call_count += 1
        results = []
        content = messages[1]["content"]
        lines = [l for l in content.split("\n") if l.strip().startswith(("1.", "2.", "3.", "4.", "5."))]
        for i in range(len(lines)):
            results.append({"fact": i + 1, "tags": [f"gen-tag-{i}"]})
        return json.dumps({"results": results})

    with patch(
        "artiFACT.modules.facts.smart_tags.AIProvider.complete",
        mock_complete,
    ):
        results = await generate_tags_batch(db, child_node.node_uid, admin_user)

    assert len(results) == 3
    assert versions[0].version_uid not in results
    assert versions[1].version_uid not in results


async def test_generate_batch_groups_by_8(
    db: AsyncSession, admin_user: FcUser, child_node,
):
    for i in range(20):
        await create_fact(
            db, child_node.node_uid,
            f"Batch grouping fact number {i} unique {uuid.uuid4().hex[:8]}.",
            admin_user, auto_approve=True,
        )
    await db.flush()

    call_count = 0

    async def mock_complete(self, db, user_uid, messages, **kwargs):
        nonlocal call_count
        call_count += 1
        return json.dumps({"results": [
            {"fact": j + 1, "tags": [f"tag-{call_count}-{j}"]}
            for j in range(8)
        ]})

    with patch(
        "artiFACT.modules.facts.smart_tags.AIProvider.complete",
        mock_complete,
    ):
        await generate_tags_batch(db, child_node.node_uid, admin_user)

    assert call_count == 3


async def test_generate_batch_returns_results_dict(
    db: AsyncSession, admin_user: FcUser, child_node,
):
    _, v = await create_fact(
        db, child_node.node_uid,
        f"Single batch fact for results dict {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    mock_response = json.dumps({
        "results": [{"fact": 1, "tags": ["infrastructure", "deployment"]}]
    })

    with patch(
        "artiFACT.modules.facts.smart_tags.AIProvider.complete",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        results = await generate_tags_batch(db, child_node.node_uid, admin_user)

    assert isinstance(results, dict)
    assert v.version_uid in results
    assert isinstance(results[v.version_uid], list)


# ── Manual CRUD ──


async def test_update_tags_manual_stores_valid_tags(
    db: AsyncSession, admin_user: FcUser, child_node,
):
    _, version = await create_fact(
        db, child_node.node_uid,
        f"Manual tag test fact about systems {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    accepted, rejected = await update_tags_manual(
        db, version.version_uid, ["cloud", "hosting", "deployment"], admin_user,
    )

    assert accepted == ["cloud", "hosting", "deployment"]
    assert rejected == []
    assert version.smart_tags == ["cloud", "hosting", "deployment"]
    assert version.smart_tags_text == "cloud hosting deployment"


async def test_update_tags_manual_rejects_fact_word_tags(
    db: AsyncSession, admin_user: FcUser, child_node,
):
    _, version = await create_fact(
        db, child_node.node_uid,
        f"PostgreSQL handles database operations {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    accepted, rejected = await update_tags_manual(
        db, version.version_uid, ["postgresql", "database", "backup"], admin_user,
    )

    assert "backup" in accepted
    assert "postgresql" in rejected
    assert "database" in rejected


async def test_update_tags_manual_requires_contribute_permission(
    db: AsyncSession, viewer_user: FcUser, admin_user: FcUser, child_node,
):
    _, version = await create_fact(
        db, child_node.node_uid,
        f"Permission test fact for tags {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    from artiFACT.kernel.exceptions import Forbidden

    with pytest.raises(Forbidden):
        await update_tags_manual(
            db, version.version_uid, ["tag1"], viewer_user,
        )


# ── Validate endpoint (unit) ──


def test_validate_tag_endpoint_logic_returns_valid_true():
    assert validate_tag("infrastructure", "FastAPI is the web framework") is True


def test_validate_tag_endpoint_logic_returns_valid_false():
    assert validate_tag("framework", "FastAPI is the web framework") is False


# ── Version carry-forward ──


async def test_edit_fact_carries_smart_tags_to_new_version(
    db: AsyncSession, admin_user: FcUser, child_node,
):
    fact, version = await create_fact(
        db, child_node.node_uid,
        f"Carry-forward test original sentence {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    version.smart_tags = ["cloud", "hosting"]
    version.smart_tags_text = "cloud hosting"
    await db.flush()

    fact, new_version = await edit_fact(
        db, fact.fact_uid,
        f"Carry-forward test edited sentence {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    assert new_version.smart_tags == ["cloud", "hosting"]
    assert new_version.smart_tags_text == "cloud hosting"


# ── Schema ──


def test_version_out_includes_smart_tags():
    from artiFACT.modules.facts.schemas import VersionOut

    fields = VersionOut.model_fields
    assert "smart_tags" in fields
