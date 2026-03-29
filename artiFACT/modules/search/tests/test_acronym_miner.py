"""Tests for acronym miner (correct table + columns, Redis cache)."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.session import get_redis
from artiFACT.kernel.events import publish
from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcUser
from artiFACT.modules.search.acronym_miner import ACRONYM_CACHE_KEY, mine_acronyms


async def _publish_fact(
    db: AsyncSession, node: FcNode, sentence: str, user: FcUser
) -> FcFactVersion:
    """Create a published fact version with the given sentence."""
    fact = FcFact(
        fact_uid=uuid.uuid4(),
        node_uid=node.node_uid,
        created_by_uid=user.user_uid,
    )
    db.add(fact)
    await db.flush()

    version = FcFactVersion(
        version_uid=uuid.uuid4(),
        fact_uid=fact.fact_uid,
        state="published",
        display_sentence=sentence,
        created_by_uid=user.user_uid,
        published_at=datetime.now(timezone.utc),
    )
    db.add(version)
    await db.flush()

    fact.current_published_version_uid = version.version_uid
    await db.flush()
    return version


async def test_acronym_query_uses_correct_table_and_columns(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode
):
    """Acronym miner queries fc_fact_version.display_sentence (v1 B-BUG-01 regression)."""
    await _publish_fact(
        db, child_node, "The DOD requires all COCOM to follow SOP procedures.", admin_user
    )
    await _publish_fact(
        db, child_node, "Network ACL rules enforce DOD policy.", admin_user
    )

    entries = await mine_acronyms(db)

    acronyms = {e["acronym"] for e in entries}
    assert "DOD" in acronyms
    assert "COCOM" in acronyms
    assert "SOP" in acronyms
    assert "ACL" in acronyms
    # DOD appears in two sentences
    dod_entry = next(e for e in entries if e["acronym"] == "DOD")
    assert dod_entry["count"] == 2


async def test_acronym_cache_invalidated_on_publish(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode
):
    """Publishing a fact fires fact.published event which clears the acronym cache."""
    await _publish_fact(
        db, child_node, "The DOD standard applies here.", admin_user
    )

    # Prime the cache
    entries = await mine_acronyms(db)
    assert any(e["acronym"] == "DOD" for e in entries)

    # Verify cache is populated
    r = await get_redis()
    assert await r.exists(ACRONYM_CACHE_KEY)

    # Fire the event (real event bus, real handler)
    await publish("fact.published", {"fact_uid": str(uuid.uuid4())})

    # Cache should be cleared
    assert not await r.exists(ACRONYM_CACHE_KEY)
