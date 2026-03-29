"""Tests for scope_resolver — verifies approval scope computation."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcNode, FcNodePermission, FcUser
from artiFACT.modules.queue.scope_resolver import get_approvable_nodes


async def test_admin_sees_all_nodes(db: AsyncSession, admin_user: FcUser, root_node, child_node):
    """Admin gets every non-archived node."""
    result = await get_approvable_nodes(db, admin_user)
    assert root_node.node_uid in result
    assert child_node.node_uid in result
    assert result[root_node.node_uid] == "admin"


async def test_subapprover_sees_granted_node_and_descendants(
    db: AsyncSession, admin_user: FcUser, root_node: FcNode, child_node: FcNode
):
    """A subapprover on root should see root + its children."""
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=Sub {uuid.uuid4().hex[:8]}",
        display_name="Sub Approver",
        global_role="viewer",
    )
    db.add(user)
    await db.flush()

    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=user.user_uid,
        node_uid=root_node.node_uid,
        role="subapprover",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()

    result = await get_approvable_nodes(db, user)
    assert root_node.node_uid in result
    assert child_node.node_uid in result
    assert result[root_node.node_uid] == "subapprover"


async def test_contributor_gets_empty_scope(
    db: AsyncSession, contributor_user: FcUser, child_node: FcNode, contributor_permission
):
    """A contributor (below subapprover) should have no approvable nodes."""
    result = await get_approvable_nodes(db, contributor_user)
    assert len(result) == 0


async def test_viewer_global_gets_empty_scope(db: AsyncSession):
    """A viewer-only user with no grants has no approvable nodes."""
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=Viewer {uuid.uuid4().hex[:8]}",
        display_name="Viewer",
        global_role="viewer",
    )
    db.add(user)
    await db.flush()

    result = await get_approvable_nodes(db, user)
    assert len(result) == 0
