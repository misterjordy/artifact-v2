"""Get ancestor chain for a node (recursive CTE)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcNode


async def get_ancestors(db: AsyncSession, node_uid: uuid.UUID) -> list[uuid.UUID]:
    """Return list of ancestor node UIDs from target up to root (inclusive)."""
    cte = (
        select(FcNode.node_uid, FcNode.parent_node_uid)
        .where(FcNode.node_uid == node_uid)
        .cte(name="chain", recursive=True)
    )
    cte = cte.union_all(
        select(FcNode.node_uid, FcNode.parent_node_uid).join(
            cte, FcNode.node_uid == cte.c.parent_node_uid
        )
    )
    result = await db.execute(select(cte.c.node_uid))
    return [row[0] for row in result.all()]
