"""Compute which nodes a user can approve."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcUser
from artiFACT.kernel.permissions.grants import get_active_grants
from artiFACT.kernel.permissions.hierarchy import role_gte
from artiFACT.kernel.tree.descendants import get_descendants


async def get_approvable_nodes(db: AsyncSession, user: FcUser) -> dict[uuid.UUID, str]:
    """Return {node_uid: role} for every node the user may approve.

    Admins get all nodes. Otherwise walk grants ≥ subapprover,
    expand each granted node to its descendants, keep highest role.
    """
    if user.global_role == "admin":
        from sqlalchemy import select

        from artiFACT.kernel.models import FcNode

        result = await db.execute(select(FcNode.node_uid).where(FcNode.is_archived.is_(False)))
        return {row[0]: "admin" for row in result.all()}

    grants = await get_active_grants(db, user.user_uid)
    node_roles: dict[uuid.UUID, str] = {}

    for grant in grants:
        if not role_gte(grant.role, "subapprover"):
            continue
        descendants = await get_descendants(db, grant.node_uid)
        for desc_uid in descendants:
            if desc_uid not in node_roles or role_gte(grant.role, node_roles[desc_uid]):
                node_roles[desc_uid] = grant.role

    return node_roles
