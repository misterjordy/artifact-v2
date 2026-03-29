"""Resolve user role for a node (with caching)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcUser
from artiFACT.kernel.permissions.cache import get_cached_role, set_cached_role
from artiFACT.kernel.permissions.grants import get_active_grants
from artiFACT.kernel.permissions.hierarchy import REQUIRED_ROLES, role_gte
from artiFACT.kernel.tree.ancestors import get_ancestors


async def resolve_role(user: FcUser, node_uid: uuid.UUID, db: AsyncSession) -> str:
    """Resolve the effective role for a user on a given node.

    1. Check Redis cache
    2. Load user grants (all active)
    3. Get ancestor chain for node
    4. Walk ancestors, find highest matching grant
    5. Compare to global_role, return the higher
    6. Cache result in Redis 5min
    """
    if user.global_role == "admin":
        return "admin"

    cached = await get_cached_role(user.user_uid, node_uid)
    if cached:
        return cached

    grants = await get_active_grants(db, user.user_uid)
    ancestors = await get_ancestors(db, node_uid)
    ancestor_set = set(ancestors)

    best_grant_role: str | None = None
    for grant in grants:
        if grant.node_uid in ancestor_set or grant.node_uid == node_uid:
            if best_grant_role is None or role_gte(grant.role, best_grant_role):
                best_grant_role = grant.role

    effective = user.global_role
    if best_grant_role and role_gte(best_grant_role, effective):
        effective = best_grant_role

    await set_cached_role(user.user_uid, node_uid, effective)
    return effective


async def can(user: FcUser, action: str, node_uid: uuid.UUID, db: AsyncSession) -> bool:
    """Check if user can perform action on node."""
    required = REQUIRED_ROLES.get(action)
    if required is None:
        return False
    role = await resolve_role(user, node_uid, db)
    return role_gte(role, required)
