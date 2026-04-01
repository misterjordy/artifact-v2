"""Fact retrieval for chat: Jaccard-search (efficient) and full-load (smart)."""

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode
from artiFACT.kernel.tree.descendants import get_descendants

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "do", "does", "did", "of", "in", "to", "for",
    "on", "at", "by", "up", "it", "its", "as", "or", "if", "no", "not",
    "so", "than", "that", "this", "with", "from",
})


def tokenize(text: str) -> set[str]:
    """Split text into lowercase word tokens, strip punctuation and stopwords."""
    words = _PUNCT.sub("", text.lower()).split()
    return {w for w in words if w and w not in _STOPWORDS}


def jaccard(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity between two token sets."""
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


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


async def _load_facts_in_scope(
    db: AsyncSession,
    program_node_uid: uuid.UUID,
    constraint_node_uids: list[uuid.UUID] | None,
    fact_filter: str,
) -> list[dict]:
    """Load facts with node titles for the given scope and filter."""
    node_uids = await _get_scope_node_uids(db, program_node_uid, constraint_node_uids)
    if not node_uids:
        return []

    # Pick the version pointer column based on filter
    version_col = (
        FcFact.current_signed_version_uid
        if fact_filter == "signed"
        else FcFact.current_published_version_uid
    )

    stmt = (
        select(FcFact, FcNode.title)
        .join(FcNode, FcFact.node_uid == FcNode.node_uid)
        .where(
            FcFact.node_uid.in_(node_uids),
            FcFact.is_retired.is_(False),
            version_col.isnot(None),
        )
        .order_by(FcNode.sort_order, FcNode.title)
    )
    result = await db.execute(stmt)
    rows = result.all()

    facts: list[dict] = []
    for fact, node_title in rows:
        version_uid = (
            fact.current_signed_version_uid
            if fact_filter == "signed"
            else fact.current_published_version_uid
        )
        ver = await db.get(FcFactVersion, version_uid)
        if ver:
            facts.append({
                "sentence": ver.display_sentence,
                "node_title": node_title,
            })
    return facts


async def retrieve_relevant_facts(
    db: AsyncSession,
    query: str,
    program_node_uid: uuid.UUID,
    constraint_node_uids: list[uuid.UUID] | None,
    fact_filter: str,
    top_n: int = 50,
    threshold: float = 0.1,
) -> list[dict]:
    """Jaccard-search query against all facts in scope.

    Returns top_n facts sorted by relevance, each as:
    {"sentence": str, "score": float, "node_title": str}

    Falls back to first 50 facts by node order if fewer than 10 exceed threshold.
    """
    all_facts = await _load_facts_in_scope(
        db, program_node_uid, constraint_node_uids, fact_filter
    )
    if not all_facts:
        return []

    query_tokens = tokenize(query)
    scored: list[dict] = []
    for fact in all_facts:
        fact_tokens = tokenize(fact["sentence"])
        score = jaccard(query_tokens, fact_tokens)
        scored.append({**fact, "score": round(score, 4)})

    above_threshold = [f for f in scored if f["score"] >= threshold]

    if len(above_threshold) < 10:
        # Fallback: return first top_n facts by original order
        return all_facts[:top_n]

    above_threshold.sort(key=lambda f: f["score"], reverse=True)
    return above_threshold[:top_n]


async def load_all_facts(
    db: AsyncSession,
    program_node_uid: uuid.UUID,
    constraint_node_uids: list[uuid.UUID] | None,
    fact_filter: str,
) -> list[dict]:
    """Load ALL facts in scope. For Smart mode."""
    return await _load_facts_in_scope(
        db, program_node_uid, constraint_node_uids, fact_filter
    )


async def estimate_scope_tokens(
    db: AsyncSession,
    program_node_uid: uuid.UUID,
    constraint_node_uids: list[uuid.UUID] | None,
    fact_filter: str,
) -> dict:
    """Count facts and estimate token cost for the given scope.

    Returns: {fact_count: int, estimated_tokens: int, warning: bool}
    Warning = true if estimated_tokens > 2000.
    Estimate: ~15 tokens per fact (average sentence length).
    """
    facts = await _load_facts_in_scope(
        db, program_node_uid, constraint_node_uids, fact_filter
    )
    fact_count = len(facts)
    estimated_tokens = fact_count * 15
    return {
        "fact_count": fact_count,
        "estimated_tokens": estimated_tokens,
        "warning": estimated_tokens > 2000,
    }
