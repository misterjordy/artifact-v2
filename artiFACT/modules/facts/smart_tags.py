"""Smart tag generation and management for atomic facts."""

import json
import math
import re
from uuid import UUID

import structlog
from nltk.stem import PorterStemmer
from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.ai_provider import AIProvider
from artiFACT.kernel.exceptions import Forbidden, NotFound
from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcUser
from artiFACT.kernel.permissions.resolver import can

from .smart_tag_prompts import (
    SMART_TAG_BATCH_SYSTEM_PROMPT,
    SMART_TAG_BATCH_USER_TEMPLATE,
    SMART_TAG_BATCH_USER_TEMPLATE_WITH_MANUAL,
    SMART_TAG_SYSTEM_PROMPT,
    SMART_TAG_USER_TEMPLATE,
    SMART_TAG_USER_TEMPLATE_WITH_MANUAL,
)

log = structlog.get_logger()
_stemmer = PorterStemmer()

MAX_TAGS = 12
BATCH_SIZE = 8
INPUT_TOKENS_PER_BATCH = 420
OUTPUT_TOKENS_PER_BATCH = 200


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


def filter_tags(
    tags: list[str],
    fact_sentence: str,
    *,
    exclude_stems: set[str] | None = None,
) -> list[str]:
    """Filter, deduplicate, and clean tags.

    1. Strip whitespace, replace underscores with spaces, lowercase.
    2. Deduplicate exact matches.
    3. Reject tags that only repeat words from the fact sentence (stemmed).
    4. Cross-tag stem dedup: skip tags whose stems are all already covered.
    5. Cap at 12.
    """
    seen: set[str] = set()
    validated: list[str] = []
    for tag in tags:
        cleaned = tag.strip().replace("_", " ").lower()
        if not cleaned or len(cleaned) < 2 or cleaned in seen:
            continue
        seen.add(cleaned)
        if validate_tag(cleaned, fact_sentence):
            validated.append(cleaned)

    # Cross-tag dedup, seeded with exclude_stems (e.g. from manual tags)
    seen_stems: set[str] = set(exclude_stems or set())
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
    """Rebuild smart_tags_text from auto + manual tags."""
    all_tags = list(version.smart_tags or []) + list(version.smart_tags_manual or [])
    version.smart_tags_text = " ".join(all_tags)


def _get_manual_stems(manual_tags: list[str]) -> set[str]:
    """Extract stems from manual tags for exclusion in auto-gen."""
    stems: set[str] = set()
    for mt in manual_tags:
        for w in re.findall(r"[A-Za-z0-9]+", mt):
            if len(w) > 2:
                stems.add(stem_word(w))
    return stems


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


async def _load_sibling_node_names(
    db: AsyncSession,
    node: FcNode,
    limit: int = 10,
) -> str:
    """Load sibling node titles (same parent, excluding this node)."""
    if not node.parent_node_uid:
        return "(none)"
    stmt = (
        select(FcNode.title)
        .where(FcNode.parent_node_uid == node.parent_node_uid)
        .where(FcNode.node_uid != node.node_uid)
        .where(FcNode.is_archived.is_(False))
        .order_by(FcNode.sort_order, FcNode.title)
        .limit(limit)
    )
    result = await db.execute(stmt)
    names = [row[0] for row in result]
    return "\n".join(f"- {n}" for n in names) if names else "(none)"


async def _load_published_versions(
    db: AsyncSession,
    node_uid: UUID,
    *,
    untagged_only: bool = False,
) -> list[FcFactVersion]:
    """Load published/signed versions for facts in a node."""
    stmt = (
        select(FcFactVersion)
        .join(FcFact, FcFact.fact_uid == FcFactVersion.fact_uid)
        .where(FcFact.node_uid == node_uid)
        .where(FcFact.is_retired.is_(False))
        .where(FcFactVersion.state.in_(["published", "signed"]))
        .order_by(FcFactVersion.created_at.asc())
    )
    if untagged_only:
        stmt = stmt.where(FcFactVersion.smart_tags == cast([], PG_JSONB))
    result = await db.execute(stmt)
    return list(result.scalars().all())


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

    manual_tags = list(version.smart_tags_manual or [])
    if manual_tags:
        user_content = SMART_TAG_USER_TEMPLATE_WITH_MANUAL.format(
            target_fact=version.display_sentence,
            manual_tags=", ".join(manual_tags),
            numbered_siblings=numbered,
        )
    else:
        user_content = SMART_TAG_USER_TEMPLATE.format(
            target_fact=version.display_sentence,
            numbered_siblings=numbered,
        )

    messages = [
        {"role": "system", "content": SMART_TAG_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    provider = AIProvider()
    raw = await provider.complete(
        db, actor.user_uid, messages,
        response_format={"type": "json_object"},
        max_tokens=512,
        action="smart_tags",
    )

    tags = _parse_single_response(raw)
    manual_stems = _get_manual_stems(manual_tags)
    filtered = filter_tags(tags, version.display_sentence, exclude_stems=manual_stems)

    version.smart_tags = filtered
    sync_tags_text(version)

    log.info("smart_tags.generated", version_uid=str(version_uid), count=len(filtered))
    return filtered


async def generate_tags_batch(
    db: AsyncSession,
    node_uid: UUID,
    actor: FcUser,
    *,
    replace: bool = False,
) -> dict:
    """Generate smart tags for facts in a node.

    replace=False: only process facts with empty smart_tags.
    replace=True: clear auto tags per-batch, regenerate. Manual tags untouched.

    Returns: {"tagged_count": int, "skipped_count": int, "results": {uid: [tags]}}
    """
    node = await db.get(FcNode, node_uid)
    if not node:
        raise NotFound("Node not found", code="NODE_NOT_FOUND")

    sibling_node_names = await _load_sibling_node_names(db, node)

    if replace:
        versions = await _load_published_versions(db, node_uid)
    else:
        versions = await _load_published_versions(db, node_uid, untagged_only=True)

    total_in_node = len(await _load_published_versions(db, node_uid))
    if not versions:
        return {"tagged_count": 0, "skipped_count": total_in_node, "results": {}}

    results: dict[UUID, list[str]] = {}
    provider = AIProvider()

    for batch_start in range(0, len(versions), BATCH_SIZE):
        batch = versions[batch_start: batch_start + BATCH_SIZE]

        # If replacing, clear auto tags for THIS batch only (serial)
        if replace:
            for ver in batch:
                ver.smart_tags = []

        numbered = "\n".join(
            f"{i + 1}. {v.display_sentence}" for i, v in enumerate(batch)
        )

        # Check if any facts in batch have manual tags
        has_manual = any(v.smart_tags_manual for v in batch)
        if has_manual:
            manual_lines = []
            for i, v in enumerate(batch):
                if v.smart_tags_manual:
                    manual_lines.append(
                        f"Fact {i + 1}: {', '.join(v.smart_tags_manual)}"
                    )
            user_content = SMART_TAG_BATCH_USER_TEMPLATE_WITH_MANUAL.format(
                node_title=node.title,
                numbered_facts=numbered,
                manual_tags_per_fact="\n".join(manual_lines),
                sibling_node_names=sibling_node_names,
            )
        else:
            user_content = SMART_TAG_BATCH_USER_TEMPLATE.format(
                node_title=node.title,
                numbered_facts=numbered,
                sibling_node_names=sibling_node_names,
            )

        messages = [
            {"role": "system", "content": SMART_TAG_BATCH_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        raw = await provider.complete(
            db, actor.user_uid, messages,
            response_format={"type": "json_object"},
            max_tokens=2048,
            action="smart_tags_batch",
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
                manual_stems = _get_manual_stems(ver.smart_tags_manual or [])
                filtered = filter_tags(
                    [str(t) for t in tags], ver.display_sentence,
                    exclude_stems=manual_stems,
                )
                ver.smart_tags = filtered
                sync_tags_text(ver)
                results[ver.version_uid] = filtered

        await db.flush()

    tagged = len(results)
    skipped = total_in_node - tagged
    log.info("smart_tags.batch_done", node_uid=str(node_uid), tagged=tagged)
    return {
        "tagged_count": tagged,
        "skipped_count": skipped,
        "results": results,
    }


async def estimate_bulk_tokens(
    db: AsyncSession,
    node_uid: UUID,
    *,
    replace: bool = False,
) -> dict:
    """Estimate tokens for a bulk smart tag run."""
    if replace:
        versions = await _load_published_versions(db, node_uid)
    else:
        versions = await _load_published_versions(db, node_uid, untagged_only=True)

    fact_count = len(versions)
    batch_count = math.ceil(fact_count / BATCH_SIZE) if fact_count > 0 else 0
    est_input = batch_count * INPUT_TOKENS_PER_BATCH
    est_output = batch_count * OUTPUT_TOKENS_PER_BATCH

    return {
        "fact_count": fact_count,
        "batch_count": batch_count,
        "estimated_input_tokens": est_input,
        "estimated_output_tokens": est_output,
        "estimated_total_tokens": est_input + est_output,
    }


async def update_tags_manual(
    db: AsyncSession,
    version_uid: UUID,
    tags: list[str],
    actor: FcUser,
) -> tuple[list[str], list[str]]:
    """Update manually-added tags. Protected from auto-overwrite."""
    version = await db.get(FcFactVersion, version_uid)
    if not version:
        raise NotFound("Version not found", code="VERSION_NOT_FOUND")

    fact = await db.get(FcFact, version.fact_uid)
    if not fact:
        raise NotFound("Fact not found", code="FACT_NOT_FOUND")

    if not await can(actor, "contribute", fact.node_uid, db):
        raise Forbidden("Cannot edit tags in this node", code="FORBIDDEN")

    filtered = filter_tags(tags, version.display_sentence)
    cleaned_input = {t.strip().replace("_", " ").lower() for t in tags if t.strip()}
    rejected = sorted(cleaned_input - set(filtered))

    version.smart_tags_manual = filtered
    sync_tags_text(version)

    return filtered, rejected


async def update_tags_auto(
    db: AsyncSession,
    version_uid: UUID,
    tags: list[str],
    actor: FcUser,
) -> tuple[list[str], list[str]]:
    """Update auto-generated tags directly (e.g. remove individual auto tag)."""
    version = await db.get(FcFactVersion, version_uid)
    if not version:
        raise NotFound("Version not found", code="VERSION_NOT_FOUND")

    fact = await db.get(FcFact, version.fact_uid)
    if not fact:
        raise NotFound("Fact not found", code="FACT_NOT_FOUND")

    if not await can(actor, "contribute", fact.node_uid, db):
        raise Forbidden("Cannot edit tags in this node", code="FORBIDDEN")

    filtered = filter_tags(tags, version.display_sentence)
    cleaned_input = {t.strip().replace("_", " ").lower() for t in tags if t.strip()}
    rejected = sorted(cleaned_input - set(filtered))

    version.smart_tags = filtered
    sync_tags_text(version)

    return filtered, rejected
