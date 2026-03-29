"""Real integration tests that verify behavior — replaces test_coverage_boost.py.

Targets lowest-coverage files:
  - facts/router.py — HTTP integration tests via ASGI transport
  - queue/proposal_query.py — create proposals and query them
  - facts/reassign.py — move facts between nodes, verify permissions
  - pages.py — GET page endpoints return 200 for authenticated users

Runs against real PostgreSQL and Redis inside Docker.
NO mocking of internal systems (only dependency-inject test DB session).
"""

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.csrf import generate_csrf_token
from artiFACT.kernel.auth.session import create_session
from artiFACT.kernel.db import get_db
from artiFACT.kernel.exceptions import Forbidden
from artiFACT.kernel.models import (
    FcNode,
    FcNodePermission,
    FcUser,
)
from artiFACT.main import app
from artiFACT.modules.audit.service import flush_pending_events
from artiFACT.modules.facts.reassign import reassign_fact
from artiFACT.modules.facts.service import create_fact
from artiFACT.modules.queue.proposal_query import get_proposals, get_unsigned


# ── Fixtures ──


@pytest_asyncio.fixture
async def second_node(db: AsyncSession, root_node: FcNode, admin_user: FcUser) -> FcNode:
    """A second child node for reassign tests."""
    node = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=root_node.node_uid,
        title="Second Node",
        slug=f"second-node-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


@pytest_asyncio.fixture
async def authed_client(db: AsyncSession, admin_user: FcUser) -> AsyncIterator[AsyncClient]:
    """HTTP client with the test DB session injected and authenticated as admin."""
    session_id = await create_session(admin_user)
    csrf_token = generate_csrf_token()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"session_id": session_id, "csrf_token": csrf_token},
        headers={"x-csrf-token": csrf_token},
    ) as c:
        yield c
    app.dependency_overrides.clear()


# ── facts/router.py coverage ──


async def test_post_create_fact(
    authed_client: AsyncClient, child_node: FcNode
) -> None:
    """POST /api/v1/facts creates a fact and returns 201."""
    resp = await authed_client.post(
        "/api/v1/facts",
        json={
            "node_uid": str(child_node.node_uid),
            "sentence": f"HTTP integration test fact {uuid.uuid4().hex[:8]} for router coverage.",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["fact_uid"] is not None
    assert data["current_version"]["display_sentence"].startswith("HTTP integration test fact")


async def test_get_fact_versions(
    db: AsyncSession, authed_client: AsyncClient, admin_user: FcUser, child_node: FcNode
) -> None:
    """GET /api/v1/facts/{uid}/versions returns version history."""
    fact, version = await create_fact(
        db, child_node.node_uid, f"Versioned fact for HTTP test {uuid.uuid4().hex[:8]}.", admin_user
    )
    await flush_pending_events(db)
    await db.flush()

    resp = await authed_client.get(f"/api/v1/facts/{fact.fact_uid}/versions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(v["version_uid"] == str(version.version_uid) for v in body["data"])


async def test_post_retire_fact(
    db: AsyncSession, authed_client: AsyncClient, admin_user: FcUser, child_node: FcNode
) -> None:
    """POST /api/v1/facts/{uid}/retire retires the fact."""
    fact, _ = await create_fact(
        db, child_node.node_uid, f"Retire me via HTTP {uuid.uuid4().hex[:8]}.", admin_user
    )
    await flush_pending_events(db)
    await db.flush()

    resp = await authed_client.post(f"/api/v1/facts/{fact.fact_uid}/retire")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_retired"] is True


async def test_get_list_facts(
    db: AsyncSession, authed_client: AsyncClient, admin_user: FcUser, child_node: FcNode
) -> None:
    """GET /api/v1/facts returns a list of facts."""
    await create_fact(
        db, child_node.node_uid, f"List test fact {uuid.uuid4().hex[:8]}.", admin_user
    )
    await flush_pending_events(db)
    await db.flush()

    resp = await authed_client.get("/api/v1/facts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert len(body["data"]) >= 1


# ── queue/proposal_query.py coverage ──


async def test_get_proposals_scoped(
    db: AsyncSession,
    contributor_user: FcUser,
    child_node: FcNode,
    contributor_permission: FcNodePermission,
) -> None:
    """get_proposals returns proposed versions scoped to given nodes."""
    fact, version = await create_fact(
        db,
        child_node.node_uid,
        f"Proposed fact for queue test {uuid.uuid4().hex[:8]}.",
        contributor_user,
    )
    await db.flush()

    assert version.state == "proposed"

    proposals = await get_proposals(db, [child_node.node_uid])
    assert len(proposals) >= 1
    uids = [p["version_uid"] for p in proposals]
    assert version.version_uid in uids


async def test_get_proposals_empty_for_other_node(
    db: AsyncSession,
    contributor_user: FcUser,
    child_node: FcNode,
    contributor_permission: FcNodePermission,
) -> None:
    """get_proposals returns empty when queried for a different node."""
    await create_fact(
        db,
        child_node.node_uid,
        f"Proposal scoping test {uuid.uuid4().hex[:8]}.",
        contributor_user,
    )
    await db.flush()

    other_uid = uuid.uuid4()
    proposals = await get_proposals(db, [other_uid])
    assert len(proposals) == 0


async def test_get_unsigned_returns_published(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode
) -> None:
    """get_unsigned returns published (not yet signed) facts."""
    fact, version = await create_fact(
        db, child_node.node_uid, f"Unsigned fact test {uuid.uuid4().hex[:8]}.", admin_user
    )
    await db.flush()

    assert version.state == "published"

    unsigned = await get_unsigned(db, [child_node.node_uid])
    uids = [u["version_uid"] for u in unsigned]
    assert version.version_uid in uids


# ── facts/reassign.py coverage ──


async def test_reassign_fact_moves_between_nodes(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode, second_node: FcNode
) -> None:
    """reassign_fact moves a fact from one node to another."""
    fact, _ = await create_fact(
        db, child_node.node_uid, f"Move me between nodes {uuid.uuid4().hex[:8]}.", admin_user
    )
    await db.flush()

    assert fact.node_uid == child_node.node_uid

    moved = await reassign_fact(db, fact.fact_uid, second_node.node_uid, admin_user)
    assert moved.node_uid == second_node.node_uid


async def test_reassign_fact_forbidden_without_permission(
    db: AsyncSession,
    contributor_user: FcUser,
    child_node: FcNode,
    second_node: FcNode,
    admin_user: FcUser,
    contributor_permission: FcNodePermission,
) -> None:
    """reassign_fact raises Forbidden if actor lacks approve permission."""
    fact, _ = await create_fact(
        db, child_node.node_uid, f"Cannot move me {uuid.uuid4().hex[:8]}.", admin_user
    )
    await db.flush()

    with pytest.raises(Forbidden):
        await reassign_fact(db, fact.fact_uid, second_node.node_uid, contributor_user)


# ── pages.py coverage ──


async def test_browse_page(authed_client: AsyncClient) -> None:
    """GET /browse returns 200 for authenticated user."""
    resp = await authed_client.get("/browse")
    assert resp.status_code == 200


async def test_queue_page(authed_client: AsyncClient) -> None:
    """GET /queue returns 200 for authenticated user."""
    resp = await authed_client.get("/queue")
    assert resp.status_code == 200


async def test_chat_page(authed_client: AsyncClient) -> None:
    """GET /chat returns 200 for authenticated user."""
    resp = await authed_client.get("/chat")
    assert resp.status_code == 200


async def test_import_page(authed_client: AsyncClient) -> None:
    """GET /import returns 200 for authenticated user."""
    resp = await authed_client.get("/import")
    assert resp.status_code == 200


async def test_export_page(authed_client: AsyncClient) -> None:
    """GET /export returns 200 for authenticated user."""
    resp = await authed_client.get("/export")
    assert resp.status_code == 200


async def test_admin_page(authed_client: AsyncClient) -> None:
    """GET /admin returns 200 for admin user."""
    resp = await authed_client.get("/admin")
    assert resp.status_code == 200


async def test_browse_node_partial(
    db: AsyncSession, authed_client: AsyncClient, admin_user: FcUser, child_node: FcNode
) -> None:
    """GET /partials/browse/{node_uid} returns facts for a node (HTMX partial)."""
    await create_fact(
        db, child_node.node_uid, f"Browse partial test fact {uuid.uuid4().hex[:8]}.", admin_user
    )
    await flush_pending_events(db)
    await db.flush()

    resp = await authed_client.get(f"/partials/browse/{child_node.node_uid}")
    assert resp.status_code == 200
    assert "Browse partial test fact" in resp.text


async def test_settings_page(authed_client: AsyncClient) -> None:
    """GET /settings returns 200 for authenticated user."""
    resp = await authed_client.get("/settings")
    assert resp.status_code == 200


async def test_login_page_redirects_when_authed(authed_client: AsyncClient) -> None:
    """GET / redirects to /browse when already authenticated."""
    resp = await authed_client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/browse"
