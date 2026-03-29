"""Full-text search with ts_rank and breadcrumbs from cached in-memory tree."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode
from artiFACT.modules.search.schemas import BreadcrumbEntry, SearchResult
from artiFACT.modules.taxonomy.tree_serializer import get_breadcrumb


async def search_facts(
    db: AsyncSession,
    query: str,
    limit: int = 50,
    program_uids: list[str] | None = None,
) -> list[SearchResult]:
    """Search published/signed facts using PostgreSQL tsvector, breadcrumbs from tree cache."""
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

    # Full-text search with ts_rank ordering
    tsquery = func.plainto_tsquery("english", query)
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
    return results


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
