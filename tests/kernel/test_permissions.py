"""Permission resolver unit tests."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from artiFACT.kernel.models import FcNode, FcNodePermission, FcUser
from artiFACT.kernel.permissions.hierarchy import REQUIRED_ROLES, role_gte
from artiFACT.kernel.permissions.resolver import can, resolve_role
from artiFACT.modules.auth_admin.service import hash_password


@pytest.fixture
def admin_user() -> FcUser:
    return FcUser(
        user_uid=uuid.uuid4(),
        cac_dn="admin",
        display_name="Admin",
        global_role="admin",
        is_active=True,
    )


@pytest.fixture
def contributor_user() -> FcUser:
    return FcUser(
        user_uid=uuid.uuid4(),
        cac_dn="contributor",
        display_name="Contributor",
        global_role="contributor",
        is_active=True,
    )


@pytest.fixture
def viewer_user() -> FcUser:
    return FcUser(
        user_uid=uuid.uuid4(),
        cac_dn="viewer",
        display_name="Viewer",
        global_role="viewer",
        is_active=True,
    )


@pytest.fixture
def node_uid() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def parent_node_uid() -> uuid.UUID:
    return uuid.uuid4()


@pytest.mark.asyncio
async def test_admin_can_do_everything(admin_user: FcUser, node_uid: uuid.UUID) -> None:
    """Admin role bypasses all permission checks."""
    db = AsyncMock()

    for action in REQUIRED_ROLES:
        result = await can(admin_user, action, node_uid, db)
        assert result is True, f"Admin should be able to {action}"


@pytest.mark.asyncio
async def test_contributor_cannot_approve(
    contributor_user: FcUser, node_uid: uuid.UUID
) -> None:
    """Contributor cannot approve — requires subapprover or higher."""
    db = AsyncMock()

    with patch(
        "artiFACT.kernel.permissions.resolver.get_cached_role", return_value=None
    ), patch(
        "artiFACT.kernel.permissions.resolver.get_active_grants", return_value=[]
    ), patch(
        "artiFACT.kernel.permissions.resolver.get_ancestors", return_value=[node_uid]
    ), patch(
        "artiFACT.kernel.permissions.resolver.set_cached_role", new_callable=AsyncMock
    ):
        result = await can(contributor_user, "approve", node_uid, db)
        assert result is False


@pytest.mark.asyncio
async def test_node_grant_overrides_global_role(
    viewer_user: FcUser, node_uid: uuid.UUID
) -> None:
    """A node-level grant should elevate a viewer to approver on that node."""
    db = AsyncMock()
    grant = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=viewer_user.user_uid,
        node_uid=node_uid,
        role="approver",
        granted_by_uid=uuid.uuid4(),
        revoked_at=None,
    )

    with patch(
        "artiFACT.kernel.permissions.resolver.get_cached_role", return_value=None
    ), patch(
        "artiFACT.kernel.permissions.resolver.get_active_grants", return_value=[grant]
    ), patch(
        "artiFACT.kernel.permissions.resolver.get_ancestors", return_value=[node_uid]
    ), patch(
        "artiFACT.kernel.permissions.resolver.set_cached_role", new_callable=AsyncMock
    ):
        role = await resolve_role(viewer_user, node_uid, db)
        assert role == "approver"


@pytest.mark.asyncio
async def test_revoked_grant_not_honored(
    viewer_user: FcUser, node_uid: uuid.UUID
) -> None:
    """A revoked grant should not elevate the user's role."""
    db = AsyncMock()
    # Revoked grants are filtered by get_active_grants (WHERE revoked_at IS NULL)
    # so they won't appear in the grant list at all.

    with patch(
        "artiFACT.kernel.permissions.resolver.get_cached_role", return_value=None
    ), patch(
        "artiFACT.kernel.permissions.resolver.get_active_grants", return_value=[]
    ), patch(
        "artiFACT.kernel.permissions.resolver.get_ancestors", return_value=[node_uid]
    ), patch(
        "artiFACT.kernel.permissions.resolver.set_cached_role", new_callable=AsyncMock
    ):
        role = await resolve_role(viewer_user, node_uid, db)
        assert role == "viewer"


@pytest.mark.asyncio
async def test_grant_on_parent_inherits_to_descendants(
    viewer_user: FcUser,
) -> None:
    """A grant on a parent node should give the user that role on descendant nodes."""
    parent_uid = uuid.uuid4()
    child_uid = uuid.uuid4()
    db = AsyncMock()

    grant = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=viewer_user.user_uid,
        node_uid=parent_uid,
        role="approver",
        granted_by_uid=uuid.uuid4(),
        revoked_at=None,
    )

    # child's ancestors include parent
    with patch(
        "artiFACT.kernel.permissions.resolver.get_cached_role", return_value=None
    ), patch(
        "artiFACT.kernel.permissions.resolver.get_active_grants", return_value=[grant]
    ), patch(
        "artiFACT.kernel.permissions.resolver.get_ancestors",
        return_value=[child_uid, parent_uid],
    ), patch(
        "artiFACT.kernel.permissions.resolver.set_cached_role", new_callable=AsyncMock
    ):
        role = await resolve_role(viewer_user, child_uid, db)
        assert role == "approver"
