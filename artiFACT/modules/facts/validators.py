"""Content validation for facts."""

import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict
from artiFACT.kernel.models import FcFactVersion

MIN_SENTENCE_LENGTH = 10
MAX_SENTENCE_LENGTH = 2000

PROFANITY_WORDS = frozenset([
    "fuck", "shit", "damn", "bitch", "ass", "crap", "bastard",
])

JACCARD_THRESHOLD = 0.85


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def validate_sentence(text: str) -> None:
    """Validate sentence length and content."""
    stripped = text.strip()
    if len(stripped) < MIN_SENTENCE_LENGTH:
        raise Conflict(
            f"Sentence must be at least {MIN_SENTENCE_LENGTH} characters",
            code="SENTENCE_TOO_SHORT",
        )
    if len(stripped) > MAX_SENTENCE_LENGTH:
        raise Conflict(
            f"Sentence must be at most {MAX_SENTENCE_LENGTH} characters",
            code="SENTENCE_TOO_LONG",
        )

    words = _tokenize(stripped)
    found = words & PROFANITY_WORDS
    if found:
        raise Conflict("Content contains inappropriate language", code="PROFANITY_DETECTED")


async def validate_duplicate(
    db: AsyncSession, sentence: str, node_uid: str | object
) -> None:
    """Check for near-duplicate sentences within the same node."""
    new_tokens = _tokenize(sentence)
    if not new_tokens:
        return

    from artiFACT.kernel.models import FcFact

    stmt = (
        select(FcFactVersion.display_sentence)
        .join(FcFact, FcFact.fact_uid == FcFactVersion.fact_uid)
        .where(FcFact.node_uid == node_uid)
        .where(FcFact.is_retired.is_(False))
        .where(FcFactVersion.state.in_(["proposed", "published", "signed"]))
    )
    result = await db.execute(stmt)
    for (existing_sentence,) in result:
        existing_tokens = _tokenize(existing_sentence)
        if not existing_tokens:
            continue
        intersection = new_tokens & existing_tokens
        union = new_tokens | existing_tokens
        jaccard = len(intersection) / len(union)
        if jaccard >= JACCARD_THRESHOLD:
            raise Conflict(
                "A very similar fact already exists in this node",
                code="DUPLICATE_DETECTED",
            )


def validate_effective_date(date_str: str | None) -> None:
    """Validate YYYY-MM-DD format if provided."""
    if date_str is None:
        return
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise Conflict(
            "Effective date must be in YYYY-MM-DD format",
            code="INVALID_DATE",
        ) from exc
