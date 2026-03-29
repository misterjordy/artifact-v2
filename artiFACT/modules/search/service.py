"""Full-text search with ts_rank and breadcrumbs from cached in-memory tree."""

import re
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode
from artiFACT.modules.search.schemas import BreadcrumbEntry, SearchResult
from artiFACT.modules.taxonomy.tree_serializer import get_breadcrumb


def _build_prefix_tsquery(query: str) -> str:
    """Convert a user query into prefix-matching tsquery string.

    'stat auth' → 'stat:* & auth:*'
    """
    terms = re.findall(r"\w+", query)
    if not terms:
        return ""
    return " & ".join(f"{t}:*" for t in terms)


async def search_facts(
    db: AsyncSession,
    query: str,
    limit: int = 50,
    program_uids: list[str] | None = None,
) -> list[SearchResult]:
    """Search published/signed facts and node titles using prefix matching."""
    # Load full node tree once (in-memory cache — no N+1 CTEs per result)
    tree_result = await db.execute(
        select(FcNode)
        .where(FcNode.is_archived.is_(False))
        .order_by(FcNode.node_depth, FcNode.sort_order, FcNode.title)
    )
    all_nodes = list(tree_result.scalars().all())

    # Build set of node UIDs belonging to requested programs
    allowed_node_uids: set[str] | None = None
    if program_uids:
        allowed_node_uids = _collect_descendant_uids(all_nodes, program_uids)

    prefix_expr = _build_prefix_tsquery(query)
    if not prefix_expr:
        return []

    # Prefix-matching tsquery
    tsquery = func.to_tsquery("english", text(f"'{prefix_expr}'"))
    rank = func.ts_rank(FcFactVersion.search_vector, tsquery).label("rank")

    stmt = (
        select(FcFactVersion, FcFact.node_uid, rank)
        .join(FcFact, FcFact.fact_uid == FcFactVersion.fact_uid)
        .where(
            FcFactVersion.search_vector.op("@@")(tsquery),
            FcFact.is_retired.is_(False),
            FcFactVersion.state.in_(["published", "signed"]),
        )
        .order_by(rank.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    results: list[SearchResult] = []
    seen_fact_uids: set[uuid.UUID] = set()
    for version, node_uid, rank_val in rows:
        if allowed_node_uids and str(node_uid) not in allowed_node_uids:
            continue
        seen_fact_uids.add(version.fact_uid)
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

    # Also search node titles for prefix matches
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
            # Use a synthetic version_uid/fact_uid for node-only results
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

    # Sort: node results first (rank 2.0), then facts by rank desc
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
            # Walk again to mark all intermediates
            walk = uid
            while walk and walk not in collected:
                collected.add(walk)
                walk = parent_map.get(walk)
    return collected
