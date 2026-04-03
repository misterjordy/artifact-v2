"""Scan the fact corpus for acronyms not in the acronym list."""

import re
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcAcronym, FcFact, FcFactVersion, FcUser

log = structlog.get_logger()

# Pattern: 2+ uppercase letters, optionally with hyphens, numbers, slashes, ampersands
ACRONYM_PATTERN = re.compile(r"\b([A-Z][A-Z0-9/\-&]{1,19})\b")

# Common false positives to skip
FALSE_POSITIVES = {
    "OR", "AND", "NOT", "THE", "FOR", "ALL", "IF", "IN", "ON",
    "AT", "TO", "OF", "BY", "AN", "AS", "IS", "IT", "NO", "DO",
    "SO", "UP", "US", "WE", "HE", "BE", "II", "III", "IV",
}


async def scan_corpus_for_acronyms(db: AsyncSession) -> list[str]:
    """Find uppercase acronym-like tokens in published facts not already in fc_acronym."""
    existing_result = await db.execute(select(FcAcronym.acronym))
    existing = {r.acronym.strip().upper() for r in existing_result.all()}

    facts_result = await db.execute(
        select(FcFactVersion.display_sentence)
        .join(FcFact, FcFact.fact_uid == FcFactVersion.fact_uid)
        .where(
            FcFact.is_retired.is_(False),
            FcFactVersion.state.in_(["published", "signed"]),
            FcFact.current_published_version_uid == FcFactVersion.version_uid,
        )
    )
    sentences = [r.display_sentence for r in facts_result.all()]

    found: set[str] = set()
    for sentence in sentences:
        matches = ACRONYM_PATTERN.findall(sentence)
        for match in matches:
            clean = match.strip().upper()
            if clean not in existing and clean not in FALSE_POSITIVES and len(clean) >= 2:
                found.add(clean)

    return sorted(found)


async def scan_and_insert(
    db: AsyncSession,
    user: FcUser,
) -> dict[str, int | list[str]]:
    """Scan corpus, insert new acronyms with spelled_out=NULL."""
    new_acronyms = await scan_corpus_for_acronyms(db)

    inserted = 0
    for acro in new_acronyms:
        exists = await db.execute(
            select(FcAcronym).where(
                func.upper(FcAcronym.acronym) == acro.upper()
            ).limit(1)
        )
        if exists.scalar_one_or_none():
            continue

        db.add(FcAcronym(
            acronym=acro,
            spelled_out=None,
            created_by_uid=user.user_uid,
        ))
        inserted += 1

    await db.flush()
    log.info("acronym.corpus_scan", found=len(new_acronyms), inserted=inserted)

    return {
        "found": len(new_acronyms),
        "inserted": inserted,
        "acronyms": new_acronyms,
    }


async def detect_unknown_acronyms(
    db: AsyncSession,
    sentence: str,
    user_uid: UUID | None = None,
) -> int:
    """Scan a single fact sentence for acronyms not in fc_acronym.

    Inserts new entries with spelled_out=NULL. Returns count of new acronyms found.
    """
    matches = ACRONYM_PATTERN.findall(sentence)
    if not matches:
        return 0

    existing_result = await db.execute(select(FcAcronym.acronym))
    existing = {r.acronym.strip().upper() for r in existing_result.all()}

    inserted = 0
    for match in matches:
        clean = match.strip().upper()
        if clean in existing or clean in FALSE_POSITIVES or len(clean) < 2:
            continue

        db.add(FcAcronym(
            acronym=clean,
            spelled_out=None,
            created_by_uid=user_uid,
        ))
        existing.add(clean)
        inserted += 1

    return inserted
