"""Move a fact to a different taxonomy node."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import Forbidden, NotFound
from artiFACT.kernel.models import FcFact, FcNode, FcUser
from artiFACT.kernel.permissions.resolver import can


async def reassign_fact(
    db: AsyncSession, fact_uid: UUID, target_node_uid: UUID, actor: FcUser
) -> FcFact:
    """Reassign a fact to a different node. Requires approve on both."""
    fact = await db.get(FcFact, fact_uid)
    if not fact:
        raise NotFound("Fact not found", code="FACT_NOT_FOUND")

    if not await can(actor, "approve", fact.node_uid, db):
        raise Forbidden("No permission on source node", code="FORBIDDEN")
    if not await can(actor, "approve", target_node_uid, db):
        raise Forbidden("No permission on target node", code="FORBIDDEN")

    target = await db.get(FcNode, target_node_uid)
    if not target:
        raise NotFound("Target node not found", code="NODE_NOT_FOUND")

    old_node_uid = fact.node_uid
    fact.node_uid = target_node_uid

    await publish(
        "fact.moved",
        {
            "fact_uid": str(fact_uid),
            "old_node_uid": str(old_node_uid),
            "new_node_uid": str(target_node_uid),
            "actor_uid": str(actor.user_uid),
        },
    )

    return fact
