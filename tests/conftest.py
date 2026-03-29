"""Shared pytest fixtures for kernel and module tests."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from artiFACT.kernel.models import Base, FcNode, FcNodePermission, FcUser
from artiFACT.modules.auth_admin.service import hash_password


@pytest.fixture
def admin_user() -> FcUser:
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn="admin",
        display_name="Admin User",
        email="admin@test.com",
        global_role="admin",
        is_active=True,
        password_hash=hash_password("admin"),
    )
    return user


@pytest.fixture
def contributor_user() -> FcUser:
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn="contributor",
        display_name="Contributor User",
        email="contrib@test.com",
        global_role="contributor",
        is_active=True,
        password_hash=hash_password("contributor"),
    )
    return user


@pytest.fixture
def viewer_user() -> FcUser:
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn="viewer",
        display_name="Viewer User",
        email="viewer@test.com",
        global_role="viewer",
        is_active=True,
        password_hash=hash_password("viewer"),
    )
    return user


@pytest.fixture
def root_node() -> FcNode:
    return FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=None,
        title="Root",
        slug="root",
        node_depth=0,
    )


@pytest.fixture
def child_node(root_node: FcNode) -> FcNode:
    return FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root_node.node_uid,
        title="Child",
        slug="child",
        node_depth=1,
    )


@pytest.fixture
def grandchild_node(child_node: FcNode) -> FcNode:
    return FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=child_node.node_uid,
        title="Grandchild",
        slug="grandchild",
        node_depth=2,
    )
