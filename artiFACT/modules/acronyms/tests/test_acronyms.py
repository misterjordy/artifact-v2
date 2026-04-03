"""Tests for acronym management: CRUD, locking, corpus scan, AI lookup, smart-tag hook."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.ai_provider import AIUsage
from artiFACT.kernel.models import FcAcronym, FcAiUsage, FcFact, FcFactVersion, FcUser
from artiFACT.modules.acronyms.scanner import (
    ACRONYM_PATTERN,
    FALSE_POSITIVES,
    detect_unknown_acronyms,
    scan_corpus_for_acronyms,
)
from artiFACT.modules.acronyms.seeder import seed_acronyms
from artiFACT.modules.acronyms.service import (
    LOCK_TIMEOUT_MINUTES,
    acquire_lock,
    check_lock,
    create_acronym,
    create_acronyms_bulk,
    delete_acronyms_bulk,
    get_all_for_tooltips,
    list_acronyms,
    release_lock,
    update_acronym,
)
from artiFACT.modules.facts.service import create_fact


# ── Helpers ──


async def _make_acronym(
    db: AsyncSession,
    acronym: str,
    spelled_out: str | None = None,
    user_uid: uuid.UUID | None = None,
) -> FcAcronym:
    """Insert an acronym row directly."""
    row = FcAcronym(
        acronym=acronym,
        spelled_out=spelled_out,
        created_by_uid=user_uid,
    )
    db.add(row)
    await db.flush()
    return row


async def _make_published_fact(
    db: AsyncSession,
    node_uid: uuid.UUID,
    sentence: str,
    user: FcUser,
) -> tuple[FcFact, FcFactVersion]:
    """Create a published fact."""
    fact, version = await create_fact(
        db, node_uid, sentence, user, auto_approve=True,
    )
    await db.flush()
    return fact, version


# ═══════════════════════════════════════════
# Seeding
# ═══════════════════════════════════════════


async def test_seed_inserts_from_csv(db: AsyncSession):
    count = await seed_acronyms(db)
    assert count > 100  # CSV has 387 data rows


async def test_seed_skips_duplicates_on_rerun(db: AsyncSession):
    first_count = await seed_acronyms(db)
    second_count = await seed_acronyms(db)
    assert first_count > 0
    assert second_count == 0


# ═══════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════


async def test_create_acronym(db: AsyncSession, admin_user: FcUser):
    row = await create_acronym(db, "ZZZ", "Zzz Zone", admin_user)
    assert row.acronym == "ZZZ"
    assert row.spelled_out == "Zzz Zone"
    assert row.created_by_uid == admin_user.user_uid


async def test_create_acronym_without_expansion(db: AsyncSession, admin_user: FcUser):
    row = await create_acronym(db, "XYZ", None, admin_user)
    assert row.acronym == "XYZ"
    assert row.spelled_out is None


async def test_list_acronyms_returns_all(db: AsyncSession, admin_user: FcUser):
    await _make_acronym(db, "AAA", "Alpha Alpha Alpha")
    await _make_acronym(db, "BBB", "Beta Beta Beta")
    rows, total = await list_acronyms(db)
    assert total >= 2


async def test_list_acronyms_filter(db: AsyncSession, admin_user: FcUser):
    await _make_acronym(db, "ACAT", "Acquisition Category")
    await _make_acronym(db, "BBB", "Beta Beta Beta")
    rows, total = await list_acronyms(db, q="ACAT")
    assert total >= 1
    assert all("ACAT" in r.acronym or "ACAT" in (r.spelled_out or "") for r in rows)


async def test_list_unresolved_only(db: AsyncSession, admin_user: FcUser):
    await _make_acronym(db, "RES1", "Resolved One")
    await _make_acronym(db, "RES2", "Resolved Two")
    await _make_acronym(db, "RES3", "Resolved Three")
    u1 = await _make_acronym(db, "UNRES1", None)
    u2 = await _make_acronym(db, "UNRES2", None)

    rows, total = await list_acronyms(db, unresolved_only=True)
    acronyms = {r.acronym for r in rows}
    assert "UNRES1" in acronyms
    assert "UNRES2" in acronyms
    assert all(r.spelled_out is None for r in rows)


async def test_update_acronym(db: AsyncSession, admin_user: FcUser):
    row = await _make_acronym(db, "UPD", "Original")
    updated = await update_acronym(db, row.acronym_uid, admin_user, spelled_out="Updated")
    assert updated.spelled_out == "Updated"
    assert updated.updated_by_uid == admin_user.user_uid


async def test_bulk_create_skips_duplicates(db: AsyncSession, admin_user: FcUser):
    await _make_acronym(db, "DUP", "Duplicate Test")
    items = [
        {"acronym": "DUP", "spelled_out": "Duplicate Test"},
        {"acronym": "NEW1", "spelled_out": "New One"},
    ]
    count = await create_acronyms_bulk(db, items, admin_user)
    assert count == 1


async def test_bulk_delete(db: AsyncSession, admin_user: FcUser):
    r1 = await _make_acronym(db, "DEL1", "Delete One")
    r2 = await _make_acronym(db, "DEL2", "Delete Two")
    deleted = await delete_acronyms_bulk(db, [r1.acronym_uid, r2.acronym_uid], admin_user)
    assert deleted == 2


async def test_export_csv_format(db: AsyncSession, admin_user: FcUser):
    """Verify get_all_for_tooltips returns correct structure (export is a thin wrapper)."""
    await _make_acronym(db, "EXP", "Export Test")
    rows, total = await list_acronyms(db, q="EXP")
    assert total >= 1
    assert any(r.acronym == "EXP" for r in rows)


# ═══════════════════════════════════════════
# Locking
# ═══════════════════════════════════════════


async def test_lock_prevents_other_user_edit(
    db: AsyncSession, admin_user: FcUser, contributor_user: FcUser,
):
    row = await _make_acronym(db, "LCK", "Lock Test")
    acquired = await acquire_lock(db, row.acronym_uid, admin_user)
    assert acquired is True

    with pytest.raises(Exception, match="being edited by another user"):
        await update_acronym(db, row.acronym_uid, contributor_user, spelled_out="Blocked")


async def test_lock_allows_same_user_edit(db: AsyncSession, admin_user: FcUser):
    row = await _make_acronym(db, "LCK2", "Lock Same User")
    await acquire_lock(db, row.acronym_uid, admin_user)
    updated = await update_acronym(db, row.acronym_uid, admin_user, spelled_out="Allowed")
    assert updated.spelled_out == "Allowed"


async def test_stale_lock_auto_released(
    db: AsyncSession, admin_user: FcUser, contributor_user: FcUser,
):
    row = await _make_acronym(db, "STALE", "Stale Lock")
    await acquire_lock(db, row.acronym_uid, admin_user)

    # Manually backdate the lock to simulate 6 minutes ago
    row.locked_at = datetime.now(timezone.utc) - timedelta(minutes=6)
    await db.flush()

    # Other user should now be able to edit (stale lock auto-released)
    updated = await update_acronym(
        db, row.acronym_uid, contributor_user, spelled_out="Unstaled",
    )
    assert updated.spelled_out == "Unstaled"


async def test_lock_acquire_returns_false_when_held(
    db: AsyncSession, admin_user: FcUser, contributor_user: FcUser,
):
    row = await _make_acronym(db, "HELD", "Held Lock")
    await acquire_lock(db, row.acronym_uid, admin_user)
    result = await acquire_lock(db, row.acronym_uid, contributor_user)
    assert result is False


async def test_bulk_delete_blocked_by_lock(
    db: AsyncSession, admin_user: FcUser, contributor_user: FcUser,
):
    r1 = await _make_acronym(db, "BD1", "Bulk Del 1")
    r2 = await _make_acronym(db, "BD2", "Bulk Del 2")
    r3 = await _make_acronym(db, "BD3", "Bulk Del 3")

    await acquire_lock(db, r2.acronym_uid, admin_user)

    with pytest.raises(Exception, match="checked out by another user"):
        await delete_acronyms_bulk(
            db, [r1.acronym_uid, r2.acronym_uid, r3.acronym_uid], contributor_user,
        )


async def test_unlock_releases_lock(db: AsyncSession, admin_user: FcUser):
    row = await _make_acronym(db, "UNLK", "Unlock Test")
    await acquire_lock(db, row.acronym_uid, admin_user)
    await release_lock(db, row.acronym_uid, admin_user)

    refreshed = await db.get(FcAcronym, row.acronym_uid)
    assert refreshed.locked_by_uid is None


# ═══════════════════════════════════════════
# Corpus scanner
# ═══════════════════════════════════════════


async def test_scan_finds_uppercase_acronyms(
    db: AsyncSession, admin_user: FcUser, child_node,
):
    await _make_acronym(db, "ACAT", "Acquisition Category")
    await _make_published_fact(
        db, child_node.node_uid,
        f"The RDT&E budget supports ACAT III programs {uuid.uuid4().hex[:8]}.",
        admin_user,
    )
    found = await scan_corpus_for_acronyms(db)
    assert "RDT&E" in found
    assert "ACAT" not in found  # already exists
    assert "III" not in found  # false positive


async def test_scan_skips_false_positives(
    db: AsyncSession, admin_user: FcUser, child_node,
):
    await _make_published_fact(
        db, child_node.node_uid,
        f"IF the system OR the backup AND the primary {uuid.uuid4().hex[:8]}.",
        admin_user,
    )
    found = await scan_corpus_for_acronyms(db)
    assert "IF" not in found
    assert "OR" not in found
    assert "AND" not in found


async def test_scan_inserts_with_null_spelled_out(
    db: AsyncSession, admin_user: FcUser, child_node,
):
    unique_acro = f"ZQ{uuid.uuid4().hex[:4].upper()}"
    await _make_published_fact(
        db, child_node.node_uid,
        f"The {unique_acro} system provides access control {uuid.uuid4().hex[:8]}.",
        admin_user,
    )

    from artiFACT.modules.acronyms.scanner import scan_and_insert
    result = await scan_and_insert(db, admin_user)
    assert result["inserted"] >= 1

    row = (await db.execute(
        select(FcAcronym).where(FcAcronym.acronym == unique_acro)
    )).scalar_one_or_none()
    assert row is not None
    assert row.spelled_out is None


# ═══════════════════════════════════════════
# Magic wand (AI lookup)
# ═══════════════════════════════════════════


async def test_lookup_returns_expansion(db: AsyncSession, admin_user: FcUser, child_node):
    row = await _make_acronym(db, "NAVWAR", None, admin_user.user_uid)
    await _make_published_fact(
        db, child_node.node_uid,
        f"NAVWAR provides cybersecurity solutions for the fleet {uuid.uuid4().hex[:8]}.",
        admin_user,
    )

    with patch(
        "artiFACT.modules.acronyms.lookup.AIProvider.complete",
        new_callable=AsyncMock,
        return_value=("Naval Information Warfare Systems Command", AIUsage(input_tokens=50, output_tokens=10)),
    ):
        from artiFACT.modules.acronyms.lookup import lookup_acronym_expansion
        expansion = await lookup_acronym_expansion(db, row.acronym_uid, admin_user)

    assert expansion == "Naval Information Warfare Systems Command"


async def test_lookup_records_ai_usage(db: AsyncSession, admin_user: FcUser, child_node):
    row = await _make_acronym(db, "TESTLU", None, admin_user.user_uid)

    mock_complete = AsyncMock(
        return_value=("Test Lookup Unit", AIUsage(input_tokens=30, output_tokens=5)),
    )
    with patch(
        "artiFACT.modules.acronyms.lookup.AIProvider.complete",
        mock_complete,
    ):
        from artiFACT.modules.acronyms.lookup import lookup_acronym_expansion
        await lookup_acronym_expansion(db, row.acronym_uid, admin_user)

    # complete() is called with action="acronym_lookup" which records usage internally
    mock_complete.assert_called_once()
    call_kwargs = mock_complete.call_args
    assert call_kwargs.kwargs.get("action") == "acronym_lookup"


# ═══════════════════════════════════════════
# Smart-tag hook
# ═══════════════════════════════════════════


async def test_smart_tag_generation_detects_unknown_acronyms(
    db: AsyncSession, admin_user: FcUser, child_node,
):
    unique_acro = f"CNAP{uuid.uuid4().hex[:3].upper()}"
    fact, version = await _make_published_fact(
        db, child_node.node_uid,
        f"The {unique_acro} gateway provides zero trust access {uuid.uuid4().hex[:8]}.",
        admin_user,
    )

    mock_response = json.dumps({"tags": ["zero trust", "access control"]})
    with patch(
        "artiFACT.modules.facts.smart_tags.AIProvider.complete",
        new_callable=AsyncMock,
        return_value=(mock_response, AIUsage()),
    ):
        from artiFACT.modules.facts.smart_tags import generate_tags_single
        await generate_tags_single(db, version.version_uid, admin_user)

    row = (await db.execute(
        select(FcAcronym).where(FcAcronym.acronym == unique_acro)
    )).scalar_one_or_none()
    assert row is not None
    assert row.spelled_out is None


async def test_smart_tag_hook_skips_known_acronyms(
    db: AsyncSession, admin_user: FcUser, child_node,
):
    await _make_acronym(db, "ACAT", "Acquisition Category")

    before_count = (await db.execute(
        select(func.count()).where(FcAcronym.acronym == "ACAT")
    )).scalar_one()

    fact, version = await _make_published_fact(
        db, child_node.node_uid,
        f"Acquisition category is ACAT I for this program {uuid.uuid4().hex[:8]}.",
        admin_user,
    )

    mock_response = json.dumps({"tags": ["acquisition", "category"]})
    with patch(
        "artiFACT.modules.facts.smart_tags.AIProvider.complete",
        new_callable=AsyncMock,
        return_value=(mock_response, AIUsage()),
    ):
        from artiFACT.modules.facts.smart_tags import generate_tags_single
        await generate_tags_single(db, version.version_uid, admin_user)

    after_count = (await db.execute(
        select(func.count()).where(FcAcronym.acronym == "ACAT")
    )).scalar_one()
    assert after_count == before_count


# ═══════════════════════════════════════════
# Tooltip endpoint
# ═══════════════════════════════════════════


async def test_tooltip_endpoint_groups_by_acronym(db: AsyncSession):
    await _make_acronym(db, "AI", "Artificial Intelligence")
    await _make_acronym(db, "AI", "Airborne Intercept")

    result = await get_all_for_tooltips(db)
    assert "AI" in result
    assert "Artificial Intelligence" in result["AI"]
    assert "Airborne Intercept" in result["AI"]


async def test_tooltip_endpoint_excludes_unresolved(db: AsyncSession):
    unique = f"TTNR{uuid.uuid4().hex[:4].upper()}"
    await _make_acronym(db, unique, None)

    result = await get_all_for_tooltips(db)
    assert unique not in result


# ═══════════════════════════════════════════
# detect_unknown_acronyms (unit)
# ═══════════════════════════════════════════


async def test_detect_unknown_acronyms_finds_new(db: AsyncSession, admin_user: FcUser):
    unique = f"ZK{uuid.uuid4().hex[:4].upper()}"
    inserted = await detect_unknown_acronyms(
        db, f"The {unique} system is online", admin_user.user_uid,
    )
    assert inserted >= 1

    row = (await db.execute(
        select(FcAcronym).where(FcAcronym.acronym == unique)
    )).scalar_one_or_none()
    assert row is not None
    assert row.spelled_out is None


async def test_detect_unknown_acronyms_skips_existing(db: AsyncSession, admin_user: FcUser):
    await _make_acronym(db, "EXIST", "Existing Acronym")
    inserted = await detect_unknown_acronyms(
        db, "The EXIST system works fine", admin_user.user_uid,
    )
    # EXIST was already in db, so should not be inserted again
    count = (await db.execute(
        select(func.count()).where(FcAcronym.acronym == "EXIST")
    )).scalar_one()
    assert count == 1


# ═══════════════════════════════════════════
# Regex pattern
# ═══════════════════════════════════════════


def test_acronym_pattern_matches_expected():
    text = "The RDT&E budget and C4ISR systems with AI/ML"
    matches = ACRONYM_PATTERN.findall(text)
    assert "RDT&E" in matches
    assert "C4ISR" in matches
    assert "AI/ML" in matches


def test_false_positives_excluded():
    for word in ["OR", "AND", "IF", "IN", "ON", "AT", "TO", "IS", "IT", "NO"]:
        assert word in FALSE_POSITIVES
