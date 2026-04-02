"""BM25 fact retrieval with blended display_sentence + smart_tags scoring.

Replaces the old smart/efficient mode split. Every chat message goes
through this retriever unless the user requests full corpus.
"""

import re
import uuid
from typing import Any

import structlog
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcSystemConfig
from artiFACT.kernel.tree.descendants import get_descendants

from .intent_mapper import detect_intent
from .schemas import ScoredFact

log = structlog.get_logger()

DEFAULT_TEXT_WEIGHT = 0.4
DEFAULT_TAG_WEIGHT = 0.6


def _build_or_tsquery_str(terms: str) -> str:
    """Build an OR-joined tsquery string from space-separated terms.

    Deduplicates, strips non-alpha, joins with ' | '.
    """
    words = re.findall(r"[A-Za-z0-9]+", terms.lower())
    seen: set[str] = set()
    unique: list[str] = []
    for w in words:
        if len(w) > 1 and w not in seen:
            seen.add(w)
            unique.append(w)
    return " | ".join(unique) if unique else ""


async def _get_scope_node_uids(
    db: AsyncSession,
    program_node_uid: uuid.UUID,
    constraint_node_uids: list[uuid.UUID] | None,
) -> list[uuid.UUID]:
    """Resolve the set of node UIDs in scope."""
    if constraint_node_uids:
        all_uids: list[uuid.UUID] = []
        for uid in constraint_node_uids:
            all_uids.extend(await get_descendants(db, uid))
        return all_uids
    return await get_descendants(db, program_node_uid)


async def _get_retrieval_weights(
    db: AsyncSession,
    text_weight: float | None,
    tag_weight: float | None,
) -> tuple[float, float]:
    """Load retrieval weights from config or use defaults."""
    if text_weight is not None and tag_weight is not None:
        return text_weight, tag_weight
    config_row = await db.get(FcSystemConfig, "smart_retrieval_weights")
    if config_row and config_row.value:
        tw = config_row.value.get("text", DEFAULT_TEXT_WEIGHT)
        tgw = config_row.value.get("tag", DEFAULT_TAG_WEIGHT)
        return (
            text_weight if text_weight is not None else tw,
            tag_weight if tag_weight is not None else tgw,
        )
    return (
        text_weight if text_weight is not None else DEFAULT_TEXT_WEIGHT,
        tag_weight if tag_weight is not None else DEFAULT_TAG_WEIGHT,
    )


async def retrieve_facts(
    db: AsyncSession,
    query: str,
    scope_node_uids: list[uuid.UUID],
    *,
    limit: int = 40,
    text_weight: float | None = None,
    tag_weight: float | None = None,
) -> list[ScoredFact]:
    """Retrieve and rank facts using BM25 on text + smart tags.

    1. Expand query with intent archetype tags.
    2. Run two ts_rank scores per fact (text + tags).
    3. Blend: text_weight * text_score + tag_weight * tag_score.
    4. Return top `limit` facts ordered by blended score desc.
    """
    if not scope_node_uids:
        return []

    tw, tgw = await _get_retrieval_weights(db, text_weight, tag_weight)

    # Build OR-based tsquery: all query + intent terms joined with |
    _, intent_tags = detect_intent(query)
    all_terms = f"{query} {' '.join(intent_tags)}"
    or_str = _build_or_tsquery_str(all_terms)
    if not or_str:
        return []
    tsquery = func.to_tsquery("english", or_str)

    text_score = tw * func.coalesce(
        func.ts_rank(FcFactVersion.search_vector, tsquery), 0.0
    )
    tag_score = tgw * func.coalesce(
        func.ts_rank(
            func.to_tsvector("english", FcFactVersion.smart_tags_text),
            tsquery,
        ),
        0.0,
    )
    blended = (text_score + tag_score).label("blended_score")

    stmt = (
        select(
            FcFactVersion.version_uid,
            FcFactVersion.display_sentence,
            FcFactVersion.smart_tags,
            FcFact.node_uid,
            blended,
        )
        .join(FcFact, FcFact.fact_uid == FcFactVersion.fact_uid)
        .where(
            FcFact.is_retired.is_(False),
            FcFactVersion.state.in_(["published", "signed"]),
            FcFact.node_uid.in_(scope_node_uids),
            or_(
                FcFactVersion.search_vector.op("@@")(tsquery),
                func.to_tsvector("english", FcFactVersion.smart_tags_text).op("@@")(tsquery),
            ),
        )
        .order_by(text("blended_score DESC"))
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        ScoredFact(
            version_uid=row[0],
            display_sentence=row[1],
            smart_tags=row[2] or [],
            node_uid=row[3],
            blended_score=round(float(row[4]), 6),
        )
        for row in rows
    ]


async def load_all_facts(
    db: AsyncSession,
    scope_node_uids: list[uuid.UUID],
) -> list[ScoredFact]:
    """Load ALL published/signed facts in scope (for full-corpus mode).

    No scoring — returns facts in node + created_at order, score=1.0.
    """
    if not scope_node_uids:
        return []

    stmt = (
        select(
            FcFactVersion.version_uid,
            FcFactVersion.display_sentence,
            FcFactVersion.smart_tags,
            FcFact.node_uid,
        )
        .join(FcFact, FcFact.fact_uid == FcFactVersion.fact_uid)
        .where(
            FcFact.is_retired.is_(False),
            FcFactVersion.state.in_(["published", "signed"]),
            FcFact.node_uid.in_(scope_node_uids),
            FcFact.current_published_version_uid == FcFactVersion.version_uid,
        )
        .order_by(FcFact.node_uid, FcFactVersion.created_at.asc())
    )
    result = await db.execute(stmt)
    return [
        ScoredFact(
            version_uid=row[0],
            display_sentence=row[1],
            smart_tags=row[2] or [],
            node_uid=row[3],
            blended_score=1.0,
        )
        for row in result.all()
    ]


async def estimate_scope_tokens(
    db: AsyncSession,
    program_node_uid: uuid.UUID,
    constraint_node_uids: list[uuid.UUID] | None,
    fact_filter: str,
) -> dict[str, Any]:
    """Count facts and estimate token cost for the given scope.

    Returns: {fact_count, estimated_tokens, warning, full_corpus_token_estimate}
    """
    node_uids = await _get_scope_node_uids(db, program_node_uid, constraint_node_uids)
    if not node_uids:
        return {
            "fact_count": 0,
            "estimated_tokens": 0,
            "warning": False,
            "full_corpus_token_estimate": 0,
        }

    version_col = (
        FcFact.current_signed_version_uid
        if fact_filter == "signed"
        else FcFact.current_published_version_uid
    )
    stmt = (
        select(func.count())
        .select_from(FcFact)
        .where(
            FcFact.node_uid.in_(node_uids),
            FcFact.is_retired.is_(False),
            version_col.isnot(None),
        )
    )
    result = await db.execute(stmt)
    fact_count = result.scalar() or 0
    estimated_tokens = fact_count * 15

    return {
        "fact_count": fact_count,
        "estimated_tokens": estimated_tokens,
        "warning": estimated_tokens > 2000,
        "full_corpus_token_estimate": estimated_tokens,
    }
