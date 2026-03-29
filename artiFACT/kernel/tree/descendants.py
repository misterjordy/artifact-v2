"""Get descendant set for a node (recursive CTE)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcNode


async def get_descendants(db: AsyncSession, root_uid: uuid.UUID) -> list[uuid.UUID]:
    """Return list of all descendant node UIDs (inclusive of root)."""
    cte = (
        select(FcNode.node_uid)
        .where(FcNode.node_uid == root_uid)
        .cte(name="tree", recursive=True)
    )
    cte = cte.union_all(
        select(FcNode.node_uid).join(cte, FcNode.parent_node_uid == cte.c.node_uid)
    )
    result = await db.execute(select(cte.c.node_uid))
    return [row[0] for row in result.all()]
