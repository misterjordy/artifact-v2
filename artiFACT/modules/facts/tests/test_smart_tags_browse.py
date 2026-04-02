"""Tests for smart tags browse UX: data layer, lightbulb state, right pane data."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcFact, FcFactVersion, FcUser
from artiFACT.modules.facts.history import get_fact_history
from artiFACT.modules.facts.service import create_fact
from artiFACT.modules.facts.smart_tags import sync_tags_text


async def _get_browse_facts_with_tags(db: AsyncSession, node_uid: uuid.UUID) -> list[dict]:
    """Replicate pages._get_facts_for_node to verify smart_tags included."""
    from sqlalchemy import select
    from artiFACT.kernel.models import FcFact, FcFactVersion

    stmt = (
        select(FcFact)
        .where(
            FcFact.node_uid == node_uid,
            FcFact.is_retired.is_(False),
            FcFact.current_published_version_uid.isnot(None),
        )
        .order_by(FcFact.created_at.asc())
    )
    result = await db.execute(stmt)
    facts = result.scalars().all()

    items = []
    for fact in facts:
        ver = await db.get(FcFactVersion, fact.current_published_version_uid)
        if not ver:
            continue
        items.append({
            "fact_uid": str(fact.fact_uid),
            "version_uid": str(ver.version_uid),
            "sentence": ver.display_sentence,
            "state": ver.state,
            "smart_tags": ver.smart_tags or [],
        })
    return items


# ── Fact data includes smart_tags ──


async def test_browse_fact_data_includes_smart_tags(db: AsyncSession, admin_user, child_node):
    """Browse fact data must include smart_tags for lightbulb rendering."""
    fact, version = await create_fact(
        db, child_node.node_uid,
        f"Browse smart tags test fact {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    version.smart_tags = ["cloud", "hosting"]
    sync_tags_text(version)
    await db.flush()

    facts = await _get_browse_facts_with_tags(db, child_node.node_uid)
    assert len(facts) == 1
    assert facts[0]["smart_tags"] == ["cloud", "hosting"]
    assert facts[0]["version_uid"] == str(version.version_uid)


async def test_browse_fact_data_empty_tags_for_untagged(db: AsyncSession, admin_user, child_node):
    """Untagged facts should have empty smart_tags list."""
    await create_fact(
        db, child_node.node_uid,
        f"Untagged browse fact {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    facts = await _get_browse_facts_with_tags(db, child_node.node_uid)
    assert len(facts) == 1
    assert facts[0]["smart_tags"] == []


# ── Lightbulb state (data-driven) ──


async def test_lightbulb_lit_for_tagged_fact(db: AsyncSession, admin_user, child_node):
    """Tagged facts have non-empty smart_tags — lightbulb should be lit (yellow)."""
    fact, version = await create_fact(
        db, child_node.node_uid,
        f"Tagged lightbulb fact {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    version.smart_tags = ["infrastructure"]
    sync_tags_text(version)
    await db.flush()

    facts = await _get_browse_facts_with_tags(db, child_node.node_uid)
    assert len(facts[0]["smart_tags"]) > 0


async def test_lightbulb_unlit_for_untagged_fact(db: AsyncSession, admin_user, child_node):
    """Untagged facts have empty smart_tags — lightbulb should be unlit (gray)."""
    await create_fact(
        db, child_node.node_uid,
        f"Unlit lightbulb fact {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    facts = await _get_browse_facts_with_tags(db, child_node.node_uid)
    assert facts[0]["smart_tags"] == []


# ── Right pane shows smart tags data ──


async def test_right_pane_includes_smart_tags_data(db: AsyncSession, admin_user, child_node):
    """get_fact_history must return current_smart_tags for the right pane editor."""
    fact, version = await create_fact(
        db, child_node.node_uid,
        f"Right pane smart tags test {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    version.smart_tags = ["compliance", "audit"]
    sync_tags_text(version)
    await db.flush()

    data = await get_fact_history(db, fact.fact_uid, admin_user)
    assert data["current_smart_tags"] == ["compliance", "audit"]
    assert data["current_version_uid"] == version.version_uid


async def test_right_pane_empty_tags_for_untagged(db: AsyncSession, admin_user, child_node):
    """Right pane data returns empty smart tags for untagged facts."""
    fact, version = await create_fact(
        db, child_node.node_uid,
        f"Right pane untagged test {uuid.uuid4().hex[:8]}.",
        admin_user, auto_approve=True,
    )
    await db.flush()

    data = await get_fact_history(db, fact.fact_uid, admin_user)
    assert data["current_smart_tags"] == []
    assert data["current_version_uid"] == version.version_uid
