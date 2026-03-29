"""Load available programs/topics scoped to user's readable nodes (fixes v1 A-SEC-03)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcUser
from artiFACT.kernel.permissions.resolver import can


async def get_available_context(
    db: AsyncSession,
    user: FcUser,
) -> dict:
    """Return node tree filtered to only nodes the user can read."""
    result = await db.execute(
        select(FcNode)
        .where(FcNode.is_archived.is_(False))
        .order_by(FcNode.node_depth, FcNode.sort_order, FcNode.title)
    )
    all_nodes = list(result.scalars().all())

    readable: list[FcNode] = []
    for node in all_nodes:
        if await can(user, "read", node.node_uid, db):
            readable.append(node)

    programs = [n for n in readable if n.node_depth == 0]
    readable_set = {n.node_uid for n in readable}
    topics: dict[str, list[FcNode]] = {}
    for prog in programs:
        topics[str(prog.node_uid)] = [
            n for n in readable
            if n.node_depth > 0 and _is_descendant(n, prog.node_uid, readable_set, all_nodes)
        ]

    return {"programs": programs, "topics": topics}


def _is_descendant(
    node: FcNode,
    root_uid: uuid.UUID,
    readable_set: set[uuid.UUID],
    all_nodes: list[FcNode],
) -> bool:
    """Walk up the parent chain to see if node descends from root_uid."""
    node_map = {n.node_uid: n for n in all_nodes}
    current = node
    while current.parent_node_uid is not None:
        if current.parent_node_uid == root_uid:
            return True
        parent = node_map.get(current.parent_node_uid)
        if parent is None:
            break
        current = parent
    return False


async def get_facts_for_context(
    db: AsyncSession,
    user: FcUser,
    node_uid: uuid.UUID,
) -> tuple[list[str], int]:
    """Load published fact sentences for a node the user can read.

    Returns (sentences, total_count).
    """
    if not await can(user, "read", node_uid, db):
        return [], 0

    stmt = (
        select(FcFact)
        .where(FcFact.node_uid == node_uid, FcFact.is_retired.is_(False))
    )
    result = await db.execute(stmt)
    facts = result.scalars().all()

    sentences: list[str] = []
    for fact in facts:
        version_uid = fact.current_published_version_uid or fact.current_signed_version_uid
        if version_uid:
            ver = await db.get(FcFactVersion, version_uid)
            if ver:
                sentences.append(ver.display_sentence)

    return sentences, len(sentences)
