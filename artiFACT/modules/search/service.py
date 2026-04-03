"""Full-text search with blended BM25 on sentence + smart tags, grouped by program."""

import re
import uuid
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcSystemConfig
from artiFACT.kernel.tsquery import build_or_tsquery
from artiFACT.modules.search.schemas import (
    BreadcrumbEntry,
    GroupedSearchResult,
    ProgramGroup,
    SearchResult,
)
from artiFACT.modules.taxonomy.tree_serializer import (
    build_breadcrumb_str,
    get_breadcrumb,
    get_program_for_node,
)

DEFAULT_TEXT_WEIGHT = 0.4
DEFAULT_TAG_WEIGHT = 0.6


def _build_prefix_tsquery(query: str) -> str:
    """Convert a user query into prefix-matching tsquery string.

    'stat auth' → 'stat:* & auth:*'
    """
    terms = re.findall(r"\w+", query)
    if not terms:
        return ""
    return " & ".join(f"{t}:*" for t in terms)


async def _load_tree(db: AsyncSession) -> list[FcNode]:
    """Load the full non-archived node tree."""
    result = await db.execute(
        select(FcNode)
        .where(FcNode.is_archived.is_(False))
        .order_by(FcNode.node_depth, FcNode.sort_order, FcNode.title)
    )
    return list(result.scalars().all())


async def _get_weights(db: AsyncSession) -> tuple[float, float]:
    """Load blended scoring weights from fc_system_config or use defaults."""
    config_row = await db.get(FcSystemConfig, "smart_retrieval_weights")
    if config_row and config_row.value:
        tw = config_row.value.get("text", DEFAULT_TEXT_WEIGHT)
        tgw = config_row.value.get("tag", DEFAULT_TAG_WEIGHT)
        return float(tw), float(tgw)
    return DEFAULT_TEXT_WEIGHT, DEFAULT_TAG_WEIGHT


def _group_results_by_program(
    all_nodes: list[FcNode],
    rows: list[Any],
) -> list[ProgramGroup]:
    """Group search result rows under their program ancestor."""
    program_groups: dict[uuid.UUID | None, ProgramGroup] = {}

    for row in rows:
        program_node = get_program_for_node(all_nodes, row.node_uid)
        program_uid = program_node.node_uid if program_node else None
        program_title = program_node.title if program_node else "Unknown"

        if program_uid not in program_groups:
            program_groups[program_uid] = ProgramGroup(
                program_uid=str(program_uid) if program_uid else "unknown",
                program_title=program_title,
                results=[],
            )

        program_groups[program_uid].results.append(
            GroupedSearchResult(
                fact_uid=str(row.fact_uid),
                version_uid=str(row.version_uid),
                display_sentence=row.display_sentence,
                state=row.state,
                node_uid=str(row.node_uid),
                score=round(float(row.score), 6),
                breadcrumb=build_breadcrumb_str(all_nodes, row.node_uid),
            )
        )

    return sorted(program_groups.values(), key=lambda g: g.program_title)


async def search_facts(
    db: AsyncSession,
    query: str,
    limit: int = 50,
    offset: int = 0,
    program_uids: list[str] | None = None,
) -> dict[str, Any]:
    """Search facts with blended BM25 on sentence + smart tags.

    Returns results grouped by program.
    """
    tsquery_str = build_or_tsquery(query)
    if not tsquery_str:
        return {"programs": [], "total": 0}

    all_nodes = await _load_tree(db)

    # Build set of allowed node UIDs if filtering by program
    allowed_node_uids: set[str] | None = None
    if program_uids:
        allowed_node_uids = _collect_descendant_uids(all_nodes, program_uids)

    tw, tgw = await _get_weights(db)
    tsquery_expr = func.to_tsquery("english", tsquery_str)

    blended_score = (
        tw * func.coalesce(
            func.ts_rank(FcFactVersion.search_vector, tsquery_expr), 0.0
        )
        + tgw * func.coalesce(
            func.ts_rank(
                func.to_tsvector("english", FcFactVersion.smart_tags_text),
                tsquery_expr,
            ),
            0.0,
        )
    ).label("score")

    stmt = (
        select(
            FcFactVersion.version_uid,
            FcFactVersion.display_sentence,
            FcFactVersion.state,
            FcFact.fact_uid,
            FcFact.node_uid,
            blended_score,
        )
        .join(FcFact, FcFact.fact_uid == FcFactVersion.fact_uid)
        .where(
            FcFact.is_retired.is_(False),
            FcFactVersion.state.in_(["published", "signed"]),
            FcFact.current_published_version_uid == FcFactVersion.version_uid,
            or_(
                FcFactVersion.search_vector.op("@@")(tsquery_expr),
                func.to_tsvector("english", FcFactVersion.smart_tags_text).op("@@")(
                    tsquery_expr
                ),
            ),
        )
        .order_by(text("score DESC"))
        .limit(limit)
        .offset(offset)
    )

    if allowed_node_uids:
        stmt = stmt.where(FcFact.node_uid.in_([uuid.UUID(u) for u in allowed_node_uids]))

    result = await db.execute(stmt)
    rows = result.all()

    grouped = _group_results_by_program(all_nodes, rows)

    return {
        "programs": [g.model_dump() for g in grouped],
        "total": len(rows),
    }


async def search_facts_flat(
    db: AsyncSession,
    query: str,
    limit: int = 50,
    program_uids: list[str] | None = None,
) -> list[SearchResult]:
    """Search facts returning flat results (for HTMX partials).

    Uses the same blended BM25 scoring but returns SearchResult list.
    """
    tsquery_str = build_or_tsquery(query)
    if not tsquery_str:
        return []

    all_nodes = await _load_tree(db)

    allowed_node_uids: set[str] | None = None
    if program_uids:
        allowed_node_uids = _collect_descendant_uids(all_nodes, program_uids)

    tw, tgw = await _get_weights(db)
    tsquery_expr = func.to_tsquery("english", tsquery_str)

    blended_score = (
        tw * func.coalesce(
            func.ts_rank(FcFactVersion.search_vector, tsquery_expr), 0.0
        )
        + tgw * func.coalesce(
            func.ts_rank(
                func.to_tsvector("english", FcFactVersion.smart_tags_text),
                tsquery_expr,
            ),
            0.0,
        )
    ).label("score")

    stmt = (
        select(FcFactVersion, FcFact.node_uid, blended_score)
        .join(FcFact, FcFact.fact_uid == FcFactVersion.fact_uid)
        .where(
            FcFact.is_retired.is_(False),
            FcFactVersion.state.in_(["published", "signed"]),
            FcFact.current_published_version_uid == FcFactVersion.version_uid,
            or_(
                FcFactVersion.search_vector.op("@@")(tsquery_expr),
                func.to_tsvector("english", FcFactVersion.smart_tags_text).op("@@")(
                    tsquery_expr
                ),
            ),
        )
        .order_by(text("score DESC"))
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    results: list[SearchResult] = []
    for version, node_uid, rank_val in rows:
        if allowed_node_uids and str(node_uid) not in allowed_node_uids:
            continue
        breadcrumb_nodes = get_breadcrumb(all_nodes, node_uid)
        breadcrumb = [
            BreadcrumbEntry(node_uid=n.node_uid, title=n.title, slug=n.slug)
            for n in breadcrumb_nodes
        ]
        results.append(
            SearchResult(
                version_uid=version.version_uid,
                fact_uid=version.fact_uid,
                node_uid=node_uid,
                display_sentence=version.display_sentence,
                state=version.state,
                rank=float(rank_val),
                breadcrumb=breadcrumb,
            )
        )

    # Also search node titles
    query_lower = query.lower()
    terms = re.findall(r"\w+", query_lower)
    for node in all_nodes:
        title_lower = node.title.lower()
        if all(title_lower.find(t) >= 0 for t in terms):
            if allowed_node_uids and str(node.node_uid) not in allowed_node_uids:
                continue
            breadcrumb_nodes = get_breadcrumb(all_nodes, node.node_uid)
            breadcrumb = [
                BreadcrumbEntry(node_uid=n.node_uid, title=n.title, slug=n.slug)
                for n in breadcrumb_nodes
            ]
            results.append(
                SearchResult(
                    version_uid=node.node_uid,
                    fact_uid=node.node_uid,
                    node_uid=node.node_uid,
                    display_sentence=node.title,
                    state="node",
                    rank=2.0,
                    breadcrumb=breadcrumb,
                )
            )

    results.sort(key=lambda r: r.rank, reverse=True)
    return results[:limit]


def _collect_descendant_uids(all_nodes: list[FcNode], root_uids: list[str]) -> set[str]:
    """Collect all node UIDs that are descendants of the given root UIDs (inclusive)."""
    parent_map: dict[str, str | None] = {}
    for n in all_nodes:
        parent_map[str(n.node_uid)] = str(n.parent_node_uid) if n.parent_node_uid else None

    roots = set(root_uids)
    collected: set[str] = set(roots)
    for uid, parent in parent_map.items():
        current = uid
        while current and current not in collected:
            current = parent_map.get(current)
        if current and current in collected:
            walk = uid
            while walk and walk not in collected:
                collected.add(walk)
                walk = parent_map.get(walk)
    return collected
