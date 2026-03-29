"""Business logic for taxonomy (node CRUD, move, archive)."""

import re
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.session import get_redis
from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import NotFound
from artiFACT.kernel.models import FcNode, FcUser
from artiFACT.kernel.tree.descendants import get_descendants
from artiFACT.modules.taxonomy.validators import (
    validate_max_depth,
    validate_not_circular,
    validate_title_unique,
)

TREE_CACHE_KEY = "taxonomy:tree"


def _slugify(title: str) -> str:
    """Convert title to URL-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-")


async def _invalidate_tree_cache() -> None:
    """Delete the cached tree from Redis."""
    r = await get_redis()
    await r.delete(TREE_CACHE_KEY)


async def _get_node_or_404(db: AsyncSession, node_uid: uuid.UUID) -> FcNode:
    """Fetch a node by UID or raise NotFound."""
    result = await db.execute(select(FcNode).where(FcNode.node_uid == node_uid))
    node = result.scalar_one_or_none()
    if node is None:
        raise NotFound("Node not found")
    return node


async def create_node(
    db: AsyncSession,
    title: str,
    parent_uid: uuid.UUID | None,
    sort_order: int,
    actor: FcUser,
) -> FcNode:
    """Create a new taxonomy node.

    Validates parent exists, computes depth, checks depth <= 5,
    checks title unique among siblings, creates node, invalidates cache, emits event.
    """
    depth = 0
    if parent_uid is not None:
        parent = await _get_node_or_404(db, parent_uid)
        depth = parent.node_depth + 1

    validate_max_depth(depth)
    await validate_title_unique(db, title, parent_uid)

    node = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=parent_uid,
        title=title,
        slug=_slugify(title),
        node_depth=depth,
        sort_order=sort_order,
        is_archived=False,
        created_by_uid=actor.user_uid,
    )
    db.add(node)
    await db.flush()
    await _invalidate_tree_cache()
    await publish(
        "node.created",
        {
            "node_uid": str(node.node_uid),
            "title": node.title,
            "actor_uid": str(actor.user_uid),
        },
    )
    return node


async def move_node(
    db: AsyncSession,
    node_uid: uuid.UUID,
    new_parent_uid: uuid.UUID | None,
    actor: FcUser,
) -> FcNode:
    """Reparent a node, recompute depth for node and all descendants."""
    node = await _get_node_or_404(db, node_uid)

    if new_parent_uid is not None:
        await validate_not_circular(db, node_uid, new_parent_uid)
        new_parent = await _get_node_or_404(db, new_parent_uid)
        new_depth = new_parent.node_depth + 1
    else:
        new_depth = 0

    validate_max_depth(new_depth)

    old_depth = node.node_depth
    depth_delta = new_depth - old_depth

    node.parent_node_uid = new_parent_uid
    node.node_depth = new_depth

    # Update all descendants' depth
    if depth_delta != 0:
        descendant_uids = await get_descendants(db, node_uid)
        # Remove the node itself from descendants (already updated)
        descendant_uids = [uid for uid in descendant_uids if uid != node_uid]
        if descendant_uids:
            await db.execute(
                update(FcNode)
                .where(FcNode.node_uid.in_(descendant_uids))
                .values(node_depth=FcNode.node_depth + depth_delta)
            )

    await db.flush()
    await _invalidate_tree_cache()
    await publish(
        "node.moved",
        {
            "node_uid": str(node.node_uid),
            "new_parent_uid": str(new_parent_uid) if new_parent_uid else None,
            "actor_uid": str(actor.user_uid),
        },
    )
    return node


async def update_node(
    db: AsyncSession,
    node_uid: uuid.UUID,
    title: str | None,
    sort_order: int | None,
    actor: FcUser,
) -> FcNode:
    """Update a node's title and/or sort_order."""
    node = await _get_node_or_404(db, node_uid)

    if title is not None and title != node.title:
        await validate_title_unique(db, title, node.parent_node_uid)
        node.title = title
        node.slug = _slugify(title)

    if sort_order is not None:
        node.sort_order = sort_order

    await db.flush()
    await _invalidate_tree_cache()
    return node


async def archive_node(
    db: AsyncSession,
    node_uid: uuid.UUID,
    actor: FcUser,
) -> FcNode:
    """Soft-archive a node. Checks no active facts under node or descendants."""
    node = await _get_node_or_404(db, node_uid)

    # NOTE: Fact check will be added in the facts sprint.
    # For now, just archive the node.

    node.is_archived = True
    await db.flush()
    await _invalidate_tree_cache()
    await publish(
        "node.archived",
        {
            "node_uid": str(node.node_uid),
            "actor_uid": str(actor.user_uid),
        },
    )
    return node


async def get_all_nodes(db: AsyncSession) -> list[FcNode]:
    """Fetch all non-archived nodes ordered by depth then sort_order."""
    result = await db.execute(
        select(FcNode)
        .where(FcNode.is_archived.is_(False))
        .order_by(FcNode.node_depth, FcNode.sort_order, FcNode.title)
    )
    return list(result.scalars().all())


async def get_node_with_children(
    db: AsyncSession, node_uid: uuid.UUID
) -> tuple[FcNode, list[FcNode]]:
    """Fetch a single node and its direct children."""
    node = await _get_node_or_404(db, node_uid)
    result = await db.execute(
        select(FcNode)
        .where(FcNode.parent_node_uid == node_uid, FcNode.is_archived.is_(False))
        .order_by(FcNode.sort_order, FcNode.title)
    )
    children = list(result.scalars().all())
    return node, children
