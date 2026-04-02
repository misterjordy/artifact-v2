"""Smart tag generation and management for atomic facts."""

import json
import re
from uuid import UUID

import structlog
from nltk.stem import PorterStemmer
from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.ai_provider import AIProvider
from artiFACT.kernel.exceptions import Forbidden, NotFound
from artiFACT.kernel.models import FcAiUsage, FcFact, FcFactVersion, FcNode, FcUser
from artiFACT.kernel.permissions.resolver import can

from .smart_tag_prompts import (
    SMART_TAG_BATCH_SYSTEM_PROMPT,
    SMART_TAG_BATCH_USER_TEMPLATE,
    SMART_TAG_SYSTEM_PROMPT,
    SMART_TAG_USER_TEMPLATE,
)

log = structlog.get_logger()
_stemmer = PorterStemmer()

MAX_TAGS = 12
BATCH_SIZE = 8


def stem_word(word: str) -> str:
    """Porter-stem a single word."""
    return _stemmer.stem(word.lower())


def get_fact_stems(sentence: str) -> set[str]:
    """Tokenize sentence and return set of Porter stems. Skip tokens <= 2 chars."""
    tokens = re.findall(r"[A-Za-z0-9]+", sentence.lower())
    return {stem_word(t) for t in tokens if len(t) > 2}


def validate_tag(tag: str, fact_sentence: str) -> bool:
    """Return True if tag adds context (not all stemmed words already in fact)."""
    tag_tokens = re.findall(r"[A-Za-z0-9]+", tag)
    if not tag_tokens:
        return False
    tag_stems = {stem_word(t) for t in tag_tokens if len(t) > 2}
    if not tag_stems:
        return True
    fact_stems = get_fact_stems(fact_sentence)
    return not tag_stems.issubset(fact_stems)


def filter_tags(tags: list[str], fact_sentence: str) -> list[str]:
    """Validate, strip, lowercase, deduplicate, cross-tag stem dedup, cap at 12."""
    seen: set[str] = set()
    validated: list[str] = []
    for tag in tags:
        cleaned = tag.strip().lower()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        if validate_tag(cleaned, fact_sentence):
            validated.append(cleaned)

    # Cross-tag dedup: skip tags whose stems are all already covered
    seen_stems: set[str] = set()
    unique: list[str] = []
    for tag in validated:
        tag_stems = {stem_word(w) for w in re.findall(r"[A-Za-z0-9]+", tag) if len(w) > 2}
        if tag_stems and tag_stems <= seen_stems:
            continue
        seen_stems.update(tag_stems)
        unique.append(tag)
        if len(unique) >= MAX_TAGS:
            break
    return unique


def sync_tags_text(version: FcFactVersion) -> None:
    """Keep smart_tags_text in sync with smart_tags."""
    version.smart_tags_text = " ".join(version.smart_tags)


async def _load_sibling_sentences(
    db: AsyncSession,
    node_uid: UUID,
    exclude_fact_uid: UUID,
    limit: int = 10,
) -> list[str]:
    """Load up to N published/signed sibling fact sentences in the same node."""
    stmt = (
        select(FcFactVersion.display_sentence)
        .join(FcFact, FcFact.fact_uid == FcFactVersion.fact_uid)
        .where(FcFact.node_uid == node_uid)
        .where(FcFact.is_retired.is_(False))
        .where(FcFact.fact_uid != exclude_fact_uid)
        .where(FcFactVersion.state.in_(["published", "signed"]))
        .order_by(FcFactVersion.created_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [row[0] for row in result]


def _parse_single_response(raw: str) -> list[str]:
    """Parse JSON response from single-fact tag generation."""
    data = json.loads(raw)
    tags = data.get("tags", [])
    if not isinstance(tags, list):
        return []
    return [str(t) for t in tags if isinstance(t, (str, int, float))]


def _parse_batch_response(raw: str) -> list[dict]:
    """Parse JSON response from batch tag generation."""
    data = json.loads(raw)
    results = data.get("results", [])
    if not isinstance(results, list):
        return []
    return results


async def _log_ai_usage(
    db: AsyncSession,
    user_uid: UUID,
    action: str,
) -> None:
    """Log an AI usage record for tag generation."""
    usage = FcAiUsage(
        user_uid=user_uid,
        provider="user_key",
        model="",
        input_tokens=0,
        output_tokens=0,
        estimated_cost=0,
        action=action,
    )
    db.add(usage)


async def generate_tags_single(
    db: AsyncSession,
    version_uid: UUID,
    actor: FcUser,
) -> list[str]:
    """Generate smart tags for a single fact version via LLM."""
    version = await db.get(FcFactVersion, version_uid)
    if not version:
        raise NotFound("Version not found", code="VERSION_NOT_FOUND")

    fact = await db.get(FcFact, version.fact_uid)
    if not fact:
        raise NotFound("Fact not found", code="FACT_NOT_FOUND")

    siblings = await _load_sibling_sentences(db, fact.node_uid, fact.fact_uid)
    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(siblings)) or "(none)"

    messages = [
        {"role": "system", "content": SMART_TAG_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": SMART_TAG_USER_TEMPLATE.format(
                target_fact=version.display_sentence,
                numbered_siblings=numbered,
            ),
        },
    ]

    provider = AIProvider()
    raw = await provider.complete(
        db, actor.user_uid, messages,
        response_format={"type": "json_object"},
        max_tokens=512,
    )

    tags = _parse_single_response(raw)
    filtered = filter_tags(tags, version.display_sentence)

    version.smart_tags = filtered
    sync_tags_text(version)

    await _log_ai_usage(db, actor.user_uid, "smart_tags")
    log.info("smart_tags.generated", version_uid=str(version_uid), count=len(filtered))

    return filtered


async def generate_tags_batch(
    db: AsyncSession,
    node_uid: UUID,
    actor: FcUser,
) -> dict[UUID, list[str]]:
    """Generate smart tags for all untagged facts under a node."""
    node = await db.get(FcNode, node_uid)
    if not node:
        raise NotFound("Node not found", code="NODE_NOT_FOUND")

    stmt = (
        select(FcFactVersion)
        .join(FcFact, FcFact.fact_uid == FcFactVersion.fact_uid)
        .where(FcFact.node_uid == node_uid)
        .where(FcFact.is_retired.is_(False))
        .where(FcFactVersion.state.in_(["published", "signed"]))
        .where(FcFactVersion.smart_tags == cast([], PG_JSONB))
        .order_by(FcFactVersion.created_at.asc())
    )
    result = await db.execute(stmt)
    versions = list(result.scalars().all())

    if not versions:
        return {}

    results: dict[UUID, list[str]] = {}
    provider = AIProvider()

    for batch_start in range(0, len(versions), BATCH_SIZE):
        batch = versions[batch_start : batch_start + BATCH_SIZE]
        numbered = "\n".join(
            f"{i + 1}. {v.display_sentence}" for i, v in enumerate(batch)
        )

        messages = [
            {"role": "system", "content": SMART_TAG_BATCH_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": SMART_TAG_BATCH_USER_TEMPLATE.format(
                    node_title=node.title,
                    numbered_facts=numbered,
                ),
            },
        ]

        raw = await provider.complete(
            db, actor.user_uid, messages,
            response_format={"type": "json_object"},
            max_tokens=2048,
        )

        parsed = _parse_batch_response(raw)
        for entry in parsed:
            fact_num = entry.get("fact")
            tags = entry.get("tags", [])
            if not isinstance(fact_num, int) or not isinstance(tags, list):
                continue
            idx = fact_num - 1
            if 0 <= idx < len(batch):
                ver = batch[idx]
                filtered = filter_tags(
                    [str(t) for t in tags], ver.display_sentence
                )
                ver.smart_tags = filtered
                sync_tags_text(ver)
                results[ver.version_uid] = filtered

        await _log_ai_usage(db, actor.user_uid, "smart_tags_batch")

    log.info("smart_tags.batch_done", node_uid=str(node_uid), tagged=len(results))
    return results


async def update_tags_manual(
    db: AsyncSession,
    version_uid: UUID,
    tags: list[str],
    actor: FcUser,
) -> tuple[list[str], list[str]]:
    """Manually set smart tags, returning (accepted, rejected)."""
    version = await db.get(FcFactVersion, version_uid)
    if not version:
        raise NotFound("Version not found", code="VERSION_NOT_FOUND")

    fact = await db.get(FcFact, version.fact_uid)
    if not fact:
        raise NotFound("Fact not found", code="FACT_NOT_FOUND")

    if not await can(actor, "contribute", fact.node_uid, db):
        raise Forbidden("Cannot edit tags in this node", code="FORBIDDEN")

    filtered = filter_tags(tags, version.display_sentence)
    cleaned_input = {t.strip().lower() for t in tags if t.strip()}
    rejected = sorted(cleaned_input - set(filtered))

    version.smart_tags = filtered
    sync_tags_text(version)

    return filtered, rejected
