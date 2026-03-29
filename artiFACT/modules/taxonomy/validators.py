"""Taxonomy validation helpers."""

import uuid

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import Conflict
from artiFACT.kernel.models import FcNode
from artiFACT.kernel.tree.descendants import get_descendants


async def validate_title_unique(
    db: AsyncSession, title: str, parent_uid: uuid.UUID | None
) -> None:
    """Raise Conflict if a sibling with the same title already exists."""
    if parent_uid is None:
        stmt = select(FcNode).where(
            and_(
                FcNode.parent_node_uid.is_(None),
                FcNode.title == title,
                FcNode.is_archived.is_(False),
            )
        )
    else:
        stmt = select(FcNode).where(
            and_(
                FcNode.parent_node_uid == parent_uid,
                FcNode.title == title,
                FcNode.is_archived.is_(False),
            )
        )
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise Conflict("A sibling node with this title already exists")


def validate_max_depth(depth: int) -> None:
    """Raise Conflict if depth exceeds the maximum allowed (5)."""
    if depth > 5:
        raise Conflict("Maximum tree depth of 5 exceeded")


async def validate_not_circular(
    db: AsyncSession, node_uid: uuid.UUID, new_parent_uid: uuid.UUID
) -> None:
    """Raise Conflict if new_parent is a descendant of node (would create cycle)."""
    descendants = await get_descendants(db, node_uid)
    if new_parent_uid in descendants:
        raise Conflict("Cannot move node under its own descendant (circular reference)")
