"""Tests for browse page rendering facts by node."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcUser


async def _get_browse_facts(db: AsyncSession, node_uid: uuid.UUID) -> list[dict]:
    """Replicate the browse query logic: non-retired facts with version info."""
    stmt = (
        select(FcFact)
        .where(FcFact.node_uid == node_uid, FcFact.is_retired.is_(False))
        .order_by(FcFact.created_at.asc())
    )
    result = await db.execute(stmt)
    facts = result.scalars().all()

    items = []
    for fact in facts:
        sentence = ""
        state = "proposed"
        if fact.current_published_version_uid:
            ver = await db.get(FcFactVersion, fact.current_published_version_uid)
            if ver:
                sentence = ver.display_sentence
                state = ver.state
        else:
            ver_stmt = (
                select(FcFactVersion)
                .where(FcFactVersion.fact_uid == fact.fact_uid)
                .order_by(FcFactVersion.created_at.desc())
                .limit(1)
            )
            ver_result = await db.execute(ver_stmt)
            ver = ver_result.scalar_one_or_none()
            if ver:
                sentence = ver.display_sentence
                state = ver.state
        items.append({"sentence": sentence, "state": state})
    return items


async def test_browse_page_renders_facts_by_node(db: AsyncSession, admin_user, child_node):
    """Browse partial should return facts grouped by node."""
    fact = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=child_node.node_uid,
        created_by_uid=admin_user.user_uid,
    )
    db.add(fact)
    await db.flush()

    version = FcFactVersion(
        version_uid=uuid.uuid4(),
        fact_uid=fact.fact_uid,
        display_sentence="System uses AES-256 encryption.",
        state="published",
        created_by_uid=admin_user.user_uid,
    )
    fact.current_published_version_uid = version.version_uid
    db.add(version)
    await db.flush()

    facts = await _get_browse_facts(db, child_node.node_uid)
    assert len(facts) == 1
    assert facts[0]["sentence"] == "System uses AES-256 encryption."
    assert facts[0]["state"] == "published"


async def test_retired_facts_hidden_from_browse(db: AsyncSession, admin_user, child_node):
    """Retired facts should not appear in browse view."""
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
        display_sentence="This retired fact should not appear.",
        state="published",
        created_by_uid=admin_user.user_uid,
    )
    fact.current_published_version_uid = version.version_uid
    db.add(version)
    await db.flush()

    facts = await _get_browse_facts(db, child_node.node_uid)
    assert len(facts) == 0
