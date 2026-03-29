"""Full-text search with ts_rank and breadcrumbs from cached in-memory tree."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode
from artiFACT.modules.search.schemas import BreadcrumbEntry, SearchResult
from artiFACT.modules.taxonomy.tree_serializer import get_breadcrumb


async def search_facts(
    db: AsyncSession, query: str, limit: int = 50
) -> list[SearchResult]:
    """Search published/signed facts using PostgreSQL tsvector, breadcrumbs from tree cache."""
    # Load full node tree once (in-memory cache — no N+1 CTEs per result)
    tree_result = await db.execute(
        select(FcNode)
        .where(FcNode.is_archived.is_(False))
        .order_by(FcNode.node_depth, FcNode.sort_order, FcNode.title)
    )
    all_nodes = list(tree_result.scalars().all())

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
