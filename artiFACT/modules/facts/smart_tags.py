"""Smart tag generation and management for atomic facts."""

import json
import math
import re
from collections.abc import AsyncIterator
from uuid import UUID

import structlog
from nltk.stem import PorterStemmer
from sqlalchemy import cast, select, text
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

# Empirical token constants (from production measurements)
FIXED_INPUT_PER_BATCH = 300   # system prompt + template + sibling nodes
MARGINAL_INPUT_PER_FACT = 10  # each fact sentence in the prompt
OUTPUT_PER_FACT = 53          # ~10 tags + JSON structure per fact


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
    """Filter, deduplicate, cross-tag stem dedup, cap at 12."""
    seen: set[str] = set()
    validated: list[str] = []
    for tag in tags:
        cleaned = tag.strip().replace("_", " ").lower()
        if not cleaned or len(cleaned) < 2 or cleaned in seen:
            continue
        seen.add(cleaned)
        if validate_tag(cleaned, fact_sentence):
            validated.append(cleaned)

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


# ── Descendant traversal ──


async def get_descendant_node_uids(db: AsyncSession, node_uid: UUID) -> list[UUID]:
    """Get node_uid + all descendant node UIDs via recursive CTE."""
    result = await db.execute(
        text("""
            WITH RECURSIVE subtree AS (
                SELECT node_uid FROM fc_node WHERE node_uid = :root
                UNION ALL
                SELECT n.node_uid
                FROM fc_node n
                JOIN subtree s ON n.parent_node_uid = s.node_uid
            )
            SELECT node_uid FROM subtree
        """),
        {"root": node_uid},
    )
    return [row[0] for row in result.all()]


# ── Version loading ──


async def _load_published_versions(
    db: AsyncSession,
    node_uid: UUID,
    *,
    untagged_only: bool = False,
    include_descendants: bool = False,
) -> list[FcFactVersion]:
    """Load current published versions for facts in a node (optionally + descendants)."""
    if include_descendants:
        node_uids = await get_descendant_node_uids(db, node_uid)
    else:
        node_uids = [node_uid]

    stmt = (
        select(FcFactVersion)
        .join(FcFact, FcFact.fact_uid == FcFactVersion.fact_uid)
        .where(FcFact.is_retired.is_(False))
        .where(FcFactVersion.state.in_(["published", "signed"]))
        .where(FcFact.node_uid.in_(node_uids))
        .where(FcFact.current_published_version_uid == FcFactVersion.version_uid)
        .order_by(FcFactVersion.created_at.asc())
    )
    if untagged_only:
        stmt = stmt.where(FcFactVersion.smart_tags == cast([], PG_JSONB))
    result = await db.execute(stmt)
    return list(result.scalars().all())


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


# ── Parsing ──


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


# ── Single-fact generation ──


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
    raw, _usage = await provider.complete(
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


# ── Batch generation (with descendant traversal) ──


async def _run_single_batch(
    db: AsyncSession,
    child_node: FcNode,
    batch: list[FcFactVersion],
    sibling_node_names: str,
    provider: AIProvider,
    actor: FcUser,
    replace: bool,
) -> dict[UUID, list[str]]:
    """Run one LLM call for a single batch of facts. Returns {uid: tags}."""
    if replace:
        for ver in batch:
            ver.smart_tags = []

    numbered = "\n".join(
        f"{i + 1}. {v.display_sentence}" for i, v in enumerate(batch)
    )

    has_manual = any(v.smart_tags_manual for v in batch)
    if has_manual:
        manual_lines = [
            f"Fact {i + 1}: {', '.join(v.smart_tags_manual)}"
            for i, v in enumerate(batch) if v.smart_tags_manual
        ]
        user_content = SMART_TAG_BATCH_USER_TEMPLATE_WITH_MANUAL.format(
            node_title=child_node.title,
            numbered_facts=numbered,
            manual_tags_per_fact="\n".join(manual_lines),
            sibling_node_names=sibling_node_names,
        )
    else:
        user_content = SMART_TAG_BATCH_USER_TEMPLATE.format(
            node_title=child_node.title,
            numbered_facts=numbered,
            sibling_node_names=sibling_node_names,
        )

    messages = [
        {"role": "system", "content": SMART_TAG_BATCH_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    raw, _usage = await provider.complete(
        db, actor.user_uid, messages,
        response_format={"type": "json_object"},
        max_tokens=2048,
        action="smart_tags_batch",
    )

    results: dict[UUID, list[str]] = {}
    for entry in _parse_batch_response(raw):
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

    await db.commit()
    return results


async def generate_tags_batch_stream(
    db: AsyncSession,
    node_uid: UUID,
    actor: FcUser,
    *,
    replace: bool = False,
) -> AsyncIterator[dict]:
    """Generate smart tags, yielding progress after each batch.

    Commits per batch so partial progress survives disconnects.
    Yields: {"tagged_so_far": N, "total": N, "results": {uid: tags}}
    Final:  {"done": true, "tagged_count": N, "skipped_count": N}
    """
    # Count total facts upfront for progress denominator
    all_versions = await _load_published_versions(
        db, node_uid, untagged_only=not replace, include_descendants=True,
    )
    total_facts = len(all_versions)

    if total_facts == 0:
        yield {"done": True, "tagged_count": 0, "skipped_count": 0, "total": 0}
        return

    descendant_uids = await get_descendant_node_uids(db, node_uid)
    tagged_so_far = 0
    provider = AIProvider()

    for child_uid in descendant_uids:
        child_node = await db.get(FcNode, child_uid)
        if not child_node:
            continue

        versions = await _load_published_versions(
            db, child_uid, untagged_only=not replace,
        )
        if not versions:
            continue

        sibling_node_names = await _load_sibling_node_names(db, child_node)

        for batch_start in range(0, len(versions), BATCH_SIZE):
            batch = versions[batch_start: batch_start + BATCH_SIZE]

            batch_results = await _run_single_batch(
                db, child_node, batch, sibling_node_names,
                provider, actor, replace,
            )
            # _run_single_batch already calls db.commit()

            tagged_so_far += len(batch_results)
            yield {
                "tagged_so_far": tagged_so_far,
                "total": total_facts,
                "results": {str(k): v for k, v in batch_results.items()},
            }

    total_all = len(await _load_published_versions(
        db, node_uid, include_descendants=True,
    ))
    skipped = total_all - tagged_so_far

    log.info("smart_tags.batch_done", node_uid=str(node_uid), tagged=tagged_so_far)
    yield {
        "done": True,
        "tagged_count": tagged_so_far,
        "skipped_count": skipped,
        "total": total_facts,
    }


# ── Token estimation (empirically calibrated) ──


def estimate_bulk_tokens(fact_count: int) -> dict:
    """Estimate tokens for a bulk smart tag run.

    Based on empirical measurements from production runs:
    - 8 facts: ~382 in + ~407 out = ~789 total
    - 3 facts: ~330 in + ~168 out = ~498 total
    """
    if fact_count == 0:
        return {
            "fact_count": 0,
            "batch_count": 0,
            "estimated_input_tokens": 0,
            "estimated_output_tokens": 0,
            "estimated_total_tokens": 0,
        }

    batch_count = math.ceil(fact_count / BATCH_SIZE)
    est_input = batch_count * FIXED_INPUT_PER_BATCH + fact_count * MARGINAL_INPUT_PER_FACT
    est_output = fact_count * OUTPUT_PER_FACT

    return {
        "fact_count": fact_count,
        "batch_count": batch_count,
        "estimated_input_tokens": est_input,
        "estimated_output_tokens": est_output,
        "estimated_total_tokens": est_input + est_output,
    }


# ── Manual tag CRUD ──


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
    """Update auto-generated tags directly."""
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
