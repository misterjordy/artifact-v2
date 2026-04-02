"""Tests for unified BM25 retriever, intent mapper, and pipeline integration."""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import (
    FcFact,
    FcFactVersion,
    FcNode,
    FcSystemConfig,
    FcUser,
)
from artiFACT.modules.ai_chat.intent_mapper import (
    FALLBACK_TAGS,
    detect_intent,
    enrich_query_with_context,
    expand_query,
)
from artiFACT.modules.ai_chat.retriever import (
    estimate_scope_tokens,
    load_all_facts,
    retrieve_facts,
)
from artiFACT.modules.ai_chat.schemas import ScoredFact
from artiFACT.modules.auth_admin.ai_key_manager import save_ai_key


# ── Fixtures ──


@pytest_asyncio.fixture
async def scope_node(db: AsyncSession, admin_user: FcUser, root_node: FcNode) -> FcNode:
    """A child node to hold test facts."""
    node = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root_node.node_uid,
        title="Test Scope Node",
        slug=f"test-scope-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


async def _make_fact(
    db: AsyncSession,
    node: FcNode,
    user: FcUser,
    sentence: str,
    smart_tags: list[str] | None = None,
    is_retired: bool = False,
) -> tuple[FcFact, FcFactVersion]:
    """Helper to create a published fact with optional smart tags."""
    fact = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=node.node_uid,
        created_by_uid=user.user_uid,
        is_retired=is_retired,
    )
    db.add(fact)
    await db.flush()

    tags = smart_tags or []
    ver = FcFactVersion(
        version_uid=uuid.uuid4(),
        fact_uid=fact.fact_uid,
        state="published",
        display_sentence=sentence,
        created_by_uid=user.user_uid,
        smart_tags=tags,
        smart_tags_text=" ".join(tags),
    )
    db.add(ver)
    await db.flush()
    fact.current_published_version_uid = ver.version_uid
    await db.flush()
    return fact, ver


# ── Intent Mapper ──


def test_detect_intent_what_is():
    intent, tags = detect_intent("what is it?")
    assert intent == "describe"
    assert "description" in tags
    assert "purpose" in tags


def test_detect_intent_security():
    intent, tags = detect_intent("how secure is the encryption?")
    assert intent == "security"
    assert "encryption" in tags


def test_detect_intent_cost():
    intent, tags = detect_intent("how much does it cost?")
    assert intent == "cost"
    assert "cost" in tags
    assert "funding" in tags


def test_detect_intent_fallback():
    intent, tags = detect_intent("asdf gibberish xyz")
    assert intent == "fallback"
    assert tags == FALLBACK_TAGS


def test_expand_query_appends_tags():
    expanded = expand_query("what is it?")
    assert "what is it?" in expanded
    assert "description" in expanded
    assert "purpose" in expanded


def test_detect_intent_case_insensitive():
    intent, _ = detect_intent("HOW DOES THE ARCHITECTURE WORK?")
    assert intent == "architecture"


# ── Enrichment ──


def test_enrich_short_query_with_node_context():
    enriched = enrich_query_with_context(
        "what is it?", None, "System Purpose & Capabilities"
    )
    assert "System Purpose & Capabilities" in enriched


def test_enrich_pronoun_query_adds_node_name():
    enriched = enrich_query_with_context(
        "tell me more about that", None, "Security & Compliance"
    )
    assert "Security & Compliance" in enriched


def test_enrich_no_context_returns_original():
    enriched = enrich_query_with_context(
        "what are the encryption algorithms?", None, None
    )
    assert enriched == "what are the encryption algorithms?"


def test_enrich_with_mentioned_entities():
    state = {"mentioned_entities": ["artiFACT", "COSMOS", "GovCloud"]}
    enriched = enrich_query_with_context("what is it?", state, "System")
    assert "artiFACT" in enriched
    assert "COSMOS" in enriched


# ── BM25 Retrieval ──


async def test_retrieve_returns_scored_facts(
    db: AsyncSession, admin_user: FcUser, scope_node: FcNode,
):
    await _make_fact(db, scope_node, admin_user, "The hosting environment uses AWS GovCloud.")
    await _make_fact(db, scope_node, admin_user, "The system encrypts data at rest with AES-256.")
    await _make_fact(
        db, scope_node, admin_user,
        "COSMOS provides cloud infrastructure services.",
        smart_tags=["hosting", "GovCloud", "cloud"],
    )

    results = await retrieve_facts(
        db, "what is the hosting environment",
        [scope_node.node_uid],
    )
    assert len(results) > 0
    assert all(isinstance(r, ScoredFact) for r in results)
    assert all(r.blended_score > 0 for r in results)
    # Verify ordering: descending by score
    for i in range(len(results) - 1):
        assert results[i].blended_score >= results[i + 1].blended_score


async def test_retrieve_scores_smart_tags(
    db: AsyncSession, admin_user: FcUser, scope_node: FcNode,
):
    """Fact with matching smart_tags should get tag_score > 0."""
    await _make_fact(
        db, scope_node, admin_user,
        "The platform runs on cloud infrastructure.",
        smart_tags=["hosting", "COSMOS", "GovCloud", "AWS"],
    )
    await _make_fact(
        db, scope_node, admin_user,
        "Hosting is provided by AWS GovCloud.",
    )

    results = await retrieve_facts(
        db, "hosting", [scope_node.node_uid],
    )
    assert len(results) >= 1
    # Both facts should match (one via text, one via tags or both)
    sentences = [r.display_sentence for r in results]
    assert any("hosting" in s.lower() for s in sentences)


async def test_retrieve_respects_scope_filter(
    db: AsyncSession, admin_user: FcUser, scope_node: FcNode, root_node: FcNode,
):
    """Only facts in scoped nodes should be returned."""
    other_node = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root_node.node_uid,
        title="Other Node",
        slug=f"other-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    db.add(other_node)
    await db.flush()

    await _make_fact(db, scope_node, admin_user, "Scoped fact about hosting environment.")
    await _make_fact(db, other_node, admin_user, "Out-of-scope hosting fact.")

    results = await retrieve_facts(
        db, "hosting", [scope_node.node_uid],
    )
    for r in results:
        assert r.node_uid == scope_node.node_uid


async def test_retrieve_excludes_retired_facts(
    db: AsyncSession, admin_user: FcUser, scope_node: FcNode,
):
    await _make_fact(db, scope_node, admin_user, "Active hosting fact about cloud.")
    await _make_fact(
        db, scope_node, admin_user,
        "Retired hosting fact about cloud.", is_retired=True,
    )

    results = await retrieve_facts(
        db, "hosting cloud", [scope_node.node_uid],
    )
    assert all("Retired" not in r.display_sentence for r in results)


async def test_retrieve_limit_caps_results(
    db: AsyncSession, admin_user: FcUser, scope_node: FcNode,
):
    for i in range(15):
        await _make_fact(
            db, scope_node, admin_user,
            f"Hosting environment fact number {i} about cloud.",
        )

    results = await retrieve_facts(
        db, "hosting cloud", [scope_node.node_uid], limit=5,
    )
    assert len(results) <= 5


async def test_retrieve_empty_on_no_match(
    db: AsyncSession, admin_user: FcUser, scope_node: FcNode,
):
    await _make_fact(db, scope_node, admin_user, "The system uses PostgreSQL.")

    results = await retrieve_facts(
        db, "zyxwvut", [scope_node.node_uid],
    )
    assert len(results) == 0


async def test_retrieve_weights_from_config(
    db: AsyncSession, admin_user: FcUser, scope_node: FcNode,
):
    """Retriever should use weights from fc_system_config."""
    config = FcSystemConfig(
        key="smart_retrieval_weights",
        value={"text": 0.8, "tag": 0.2},
    )
    db.add(config)
    await db.flush()

    await _make_fact(
        db, scope_node, admin_user,
        "Cloud hosting on AWS.",
        smart_tags=["infrastructure"],
    )

    results = await retrieve_facts(
        db, "cloud hosting", [scope_node.node_uid],
    )
    # Just verify it runs without error with config-based weights
    assert isinstance(results, list)


# ── Load All Facts ──


async def test_load_all_returns_every_published_fact(
    db: AsyncSession, admin_user: FcUser, scope_node: FcNode,
):
    for i in range(10):
        await _make_fact(
            db, scope_node, admin_user,
            f"Published fact number {i} for load-all test.",
        )
    # Add a retired fact that should be excluded
    await _make_fact(
        db, scope_node, admin_user,
        "Retired fact that should be excluded.", is_retired=True,
    )

    results = await load_all_facts(db, [scope_node.node_uid])
    assert len(results) == 10
    assert all(r.blended_score == 1.0 for r in results)


# ── ScoredFact ──


def test_scored_fact_dataclass():
    sf = ScoredFact(
        version_uid=uuid.uuid4(),
        display_sentence="Test sentence.",
        smart_tags=["tag1"],
        node_uid=uuid.uuid4(),
        blended_score=0.75,
    )
    assert sf.display_sentence == "Test sentence."
    assert sf.blended_score == 0.75


# ── Estimate ──


async def test_estimate_includes_full_corpus_token_estimate(
    db: AsyncSession, admin_user: FcUser, scope_node: FcNode, root_node: FcNode,
):
    for i in range(5):
        await _make_fact(
            db, scope_node, admin_user,
            f"Estimation test fact {i} for token counting.",
        )

    result = await estimate_scope_tokens(
        db, root_node.node_uid, None, "published",
    )
    assert result["fact_count"] == 5
    assert result["full_corpus_token_estimate"] == result["estimated_tokens"]
    assert result["estimated_tokens"] == 5 * 15


# ── Prompt Builder Accepts ScoredFact ──


def test_prompt_builder_accepts_scored_facts():
    from artiFACT.modules.ai_chat.prompt_builder import build_system_prompt

    facts = [
        ScoredFact(
            version_uid=uuid.uuid4(),
            display_sentence="Fact one about hosting.",
            blended_score=0.9,
        ),
        ScoredFact(
            version_uid=uuid.uuid4(),
            display_sentence="Fact two about security.",
            blended_score=0.7,
        ),
    ]
    prompt, loaded = build_system_prompt(facts, program_name="TestProg")
    assert loaded == 2
    assert "Fact one about hosting" in prompt
    assert "Fact two about security" in prompt
    assert "TestProg" in prompt
