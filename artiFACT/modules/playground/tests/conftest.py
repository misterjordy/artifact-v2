"""Playground test fixtures."""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcNodePermission, FcUser
from artiFACT.main import app
from artiFACT.modules.auth_admin.service import hash_password
from artiFACT.scripts.seed_v1_data import (
    DWALLACE_UID,
    JALLRED_UID,
    OMARTINEZ_UID,
    PBEESLY_UID,
)


@pytest_asyncio.fixture
async def playground_users(db: AsyncSession) -> dict[str, FcUser]:
    """Create the 4 playground users."""
    users_data = [
        (JALLRED_UID, "jallred", "Jordan Allred", "admin"),
        (DWALLACE_UID, "dwallace", "David Wallace", "viewer"),
        (OMARTINEZ_UID, "omartinez", "Oscar Martinez", "viewer"),
        (PBEESLY_UID, "pbeesly", "Pam Beesly", "viewer"),
    ]
    result = {}
    for uid, cac_dn, display_name, role in users_data:
        user = FcUser(
            user_uid=uid,
            cac_dn=cac_dn,
            display_name=display_name,
            global_role=role,
            is_active=True,
            password_hash=hash_password("playground2026"),
        )
        db.add(user)
        result[cac_dn] = user
    await db.flush()
    return result


@pytest_asyncio.fixture
async def playground_nodes(db: AsyncSession, playground_users: dict) -> dict[str, FcNode]:
    """Create a minimal node tree for playground tests."""
    admin = playground_users["jallred"]
    root = FcNode(
        node_uid=uuid.uuid4(),
        title="Special Projects",
        slug="special-projects",
        node_depth=0,
        created_by_uid=admin.user_uid,
    )
    db.add(root)
    await db.flush()

    boatwing = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root.node_uid,
        title="Boatwing H-12",
        slug="boatwing-h12",
        node_depth=1,
        created_by_uid=admin.user_uid,
    )
    snipeb = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root.node_uid,
        title="SNIPE-B",
        slug="snipe-b",
        node_depth=1,
        created_by_uid=admin.user_uid,
    )
    db.add(boatwing)
    db.add(snipeb)
    await db.flush()

    return {"root": root, "boatwing": boatwing, "snipeb": snipeb}


@pytest_asyncio.fixture
async def playground_permissions(
    db: AsyncSession,
    playground_users: dict[str, FcUser],
    playground_nodes: dict[str, FcNode],
) -> None:
    """Create playground node permissions."""
    perms = [
        (DWALLACE_UID, playground_nodes["root"].node_uid, "signatory"),
        (OMARTINEZ_UID, playground_nodes["boatwing"].node_uid, "approver"),
        (OMARTINEZ_UID, playground_nodes["snipeb"].node_uid, "approver"),
        (PBEESLY_UID, playground_nodes["boatwing"].node_uid, "contributor"),
        (PBEESLY_UID, playground_nodes["snipeb"].node_uid, "contributor"),
    ]
    for user_uid, node_uid, role in perms:
        perm = FcNodePermission(
            permission_uid=uuid.uuid4(),
            user_uid=user_uid,
            node_uid=node_uid,
            role=role,
            granted_by_uid=JALLRED_UID,
        )
        db.add(perm)
    await db.flush()


@pytest.fixture
def client() -> AsyncClient:
    """HTTP client for testing playground endpoints."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")
