"""Import-pipeline-specific test fixtures."""

import uuid

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcNodePermission, FcUser


@pytest_asyncio.fixture
async def import_contributor(db: AsyncSession, root_node) -> FcUser:
    """Contributor with permission on root_node for import tests."""
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=Import Contributor {uuid.uuid4().hex[:8]}",
        display_name="Import Contributor",
        global_role="contributor",
    )
    db.add(user)
    await db.flush()

    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=user.user_uid,
        node_uid=root_node.node_uid,
        role="contributor",
        granted_by_uid=user.user_uid,
    )
    db.add(perm)
    await db.flush()
    return user
