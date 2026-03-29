"""Shared test fixtures for artiFACT tests."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from artiFACT.kernel.models import Base, FcFact, FcFactVersion, FcNode, FcNodePermission, FcUser
from artiFACT.modules.audit.recorder import register_subscribers
from artiFACT.modules.search.acronym_miner import register_subscribers as register_search_subscribers

TEST_DATABASE_URL = "postgresql+asyncpg://artifact:artifact_dev@postgres:5432/artifact_test"


@pytest.fixture(scope="session")
def _create_tables():
    """Create tables once per session (sync, outside event loop)."""
    import asyncio

    async def _setup():
        engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_setup())


@pytest_asyncio.fixture
async def db(_create_tables):
    """Per-test database session with automatic rollback."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        yield session
        await session.close()
        await trans.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession) -> FcUser:
    """Pre-created admin user."""
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=Test Admin {uuid.uuid4().hex[:8]}",
        display_name="Test Admin",
        global_role="admin",
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def approver_user(db: AsyncSession) -> FcUser:
    """Pre-created approver user."""
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=Test Approver {uuid.uuid4().hex[:8]}",
        display_name="Test Approver",
        global_role="approver",
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def contributor_user(db: AsyncSession) -> FcUser:
    """Pre-created contributor user."""
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=Test Contributor {uuid.uuid4().hex[:8]}",
        display_name="Test Contributor",
        global_role="contributor",
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def viewer_user(db: AsyncSession) -> FcUser:
    """Pre-created viewer user."""
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=Test Viewer {uuid.uuid4().hex[:8]}",
        display_name="Test Viewer",
        global_role="viewer",
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def root_node(db: AsyncSession, admin_user: FcUser) -> FcNode:
    """Pre-created root node."""
    node = FcNode(
        node_uid=uuid.uuid4(),
        title="Program A",
        slug=f"program-a-{uuid.uuid4().hex[:8]}",
        node_depth=0,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


@pytest_asyncio.fixture
async def child_node(db: AsyncSession, root_node: FcNode, admin_user: FcUser) -> FcNode:
    """Pre-created child node under root."""
    node = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root_node.node_uid,
        title="System Config",
        slug=f"system-config-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


@pytest_asyncio.fixture
async def second_node(db: AsyncSession, root_node: FcNode, admin_user: FcUser) -> FcNode:
    """A second child node for move/reassign tests."""
    node = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root_node.node_uid,
        title="Interfaces",
        slug=f"interfaces-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


@pytest_asyncio.fixture
async def approver_permission(
    db: AsyncSession, approver_user: FcUser, child_node: FcNode, admin_user: FcUser
) -> FcNodePermission:
    """Grant approver permission on child_node."""
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=approver_user.user_uid,
        node_uid=child_node.node_uid,
        role="approver",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()
    return perm


@pytest_asyncio.fixture
async def contributor_permission(
    db: AsyncSession, contributor_user: FcUser, child_node: FcNode, admin_user: FcUser
) -> FcNodePermission:
    """Grant contributor permission on child_node."""
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=contributor_user.user_uid,
        node_uid=child_node.node_uid,
        role="contributor",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()
    return perm


@pytest.fixture(autouse=True)
def _register_audit_subscribers():
    """Register audit subscribers for every test."""
    from artiFACT.kernel.events import _subscribers
    from artiFACT.modules.audit.recorder import _pending_events
    _subscribers.clear()
    _pending_events.clear()
    register_subscribers()
    register_search_subscribers()


@pytest.fixture(autouse=True)
def _reset_redis():
    """Reset Redis singleton so each test gets a fresh connection on its event loop."""
    import artiFACT.kernel.auth.session as session_mod
    session_mod._redis = None
