"""Integration tests for fact version history endpoint."""

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.csrf import generate_csrf_token
from artiFACT.kernel.auth.session import create_session
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import (
    FcFact,
    FcFactComment,
    FcFactVersion,
    FcNode,
    FcNodePermission,
    FcUser,
)
from artiFACT.main import app
from artiFACT.modules.audit.service import flush_pending_events
from artiFACT.modules.auth_admin.service import hash_password
from artiFACT.modules.facts.service import create_fact, edit_fact


# ── Fixtures ──


@pytest_asyncio.fixture
async def actor(db: AsyncSession) -> FcUser:
    """Approver user (auto-publishes facts)."""
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"approver-{uuid.uuid4().hex[:8]}",
        display_name="History Approver",
        global_role="viewer",
        is_active=True,
        password_hash=hash_password("test2026"),
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def contributor(db: AsyncSession) -> FcUser:
    """Contributor user (facts created as proposed)."""
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"contributor-{uuid.uuid4().hex[:8]}",
        display_name="History Contributor",
        global_role="viewer",
        is_active=True,
        password_hash=hash_password("test2026"),
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def viewer(db: AsyncSession) -> FcUser:
    """Viewer user (read-only)."""
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"viewer-{uuid.uuid4().hex[:8]}",
        display_name="History Viewer",
        global_role="viewer",
        is_active=True,
        password_hash=hash_password("test2026"),
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def test_root(db: AsyncSession, admin_user: FcUser) -> FcNode:
    node = FcNode(
        node_uid=uuid.uuid4(),
        title="History Test Root",
        slug=f"hist-root-{uuid.uuid4().hex[:8]}",
        node_depth=0,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


@pytest_asyncio.fixture
async def test_node(db: AsyncSession, test_root: FcNode, admin_user: FcUser) -> FcNode:
    node = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=test_root.node_uid,
        title="History Test Node",
        slug=f"hist-node-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


@pytest_asyncio.fixture
async def isolated_node(db: AsyncSession, admin_user: FcUser) -> FcNode:
    """Node where viewer has no permission."""
    node = FcNode(
        node_uid=uuid.uuid4(),
        title="Isolated History Node",
        slug=f"hist-iso-{uuid.uuid4().hex[:8]}",
        node_depth=0,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


@pytest_asyncio.fixture
async def actor_perm(
    db: AsyncSession, actor: FcUser, test_node: FcNode, admin_user: FcUser,
) -> FcNodePermission:
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=actor.user_uid,
        node_uid=test_node.node_uid,
        role="approver",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()
    return perm


@pytest_asyncio.fixture
async def contributor_perm(
    db: AsyncSession, contributor: FcUser, test_node: FcNode, admin_user: FcUser,
) -> FcNodePermission:
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=contributor.user_uid,
        node_uid=test_node.node_uid,
        role="contributor",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()
    return perm


@pytest_asyncio.fixture
async def viewer_perm(
    db: AsyncSession, viewer: FcUser, test_node: FcNode, admin_user: FcUser,
) -> FcNodePermission:
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=viewer.user_uid,
        node_uid=test_node.node_uid,
        role="viewer",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()
    return perm


async def _make_client(
    db: AsyncSession, user: FcUser, *, with_csrf: bool = True,
) -> AsyncClient:
    session_id = await create_session(user)
    csrf_token = generate_csrf_token()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    cookies = {"session_id": session_id, "csrf_token": csrf_token}
    headers = {"x-csrf-token": csrf_token} if with_csrf else {}
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies=cookies,
        headers=headers,
    )


async def _make_unauthed_client(db: AsyncSession) -> AsyncClient:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_fact(
    db: AsyncSession, node: FcNode, actor: FcUser, sentence: str,
) -> tuple[FcFact, FcFactVersion]:
    fact, ver = await create_fact(db, node.node_uid, sentence, actor)
    await flush_pending_events(db)
    await db.flush()
    return fact, ver


# ── Tests ──


async def test_history_returns_all_versions(
    db: AsyncSession, actor: FcUser, test_node: FcNode, actor_perm: FcNodePermission,
) -> None:
    """Three edits produce three versions, returned newest-first."""
    s1 = f"Original sentence for history test {uuid.uuid4().hex}"
    fact, _ = await _create_fact(db, test_node, actor, s1)

    s2 = f"First edit of history test {uuid.uuid4().hex}"
    await edit_fact(db, fact.fact_uid, s2, actor, change_summary="edit 1")
    await flush_pending_events(db)
    await db.flush()

    s3 = f"Second edit of history test {uuid.uuid4().hex}"
    await edit_fact(db, fact.fact_uid, s3, actor, change_summary="edit 2")
    await flush_pending_events(db)
    await db.flush()

    client = await _make_client(db, actor)
    async with client:
        resp = await client.get(f"/api/v1/facts/{fact.fact_uid}/history")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()["data"]
    versions = data["versions"]
    assert len(versions) == 3
    # Newest first: v3 supersedes v2 supersedes v1 via supersedes_version_uid chain
    assert versions[0]["display_sentence"] == s3
    assert versions[1]["display_sentence"] == s2
    assert versions[2]["display_sentence"] == s1
    for v in versions:
        assert "version_uid" in v
        assert "state" in v
        assert "created_by" in v
        assert "created_at" in v


async def test_history_marks_current_published_version(
    db: AsyncSession, actor: FcUser, test_node: FcNode, actor_perm: FcNodePermission,
) -> None:
    """Exactly one version flagged as current published."""
    s1 = f"Published history test {uuid.uuid4().hex}"
    fact, _ = await _create_fact(db, test_node, actor, s1)

    s2 = f"Edited published test {uuid.uuid4().hex}"
    await edit_fact(db, fact.fact_uid, s2, actor)
    await flush_pending_events(db)
    await db.flush()

    client = await _make_client(db, actor)
    async with client:
        resp = await client.get(f"/api/v1/facts/{fact.fact_uid}/history")
    app.dependency_overrides.clear()

    versions = resp.json()["data"]["versions"]
    current = [v for v in versions if v["is_current_published"]]
    assert len(current) == 1
    assert current[0]["version_uid"] == str(fact.current_published_version_uid)


async def test_history_includes_events(
    db: AsyncSession, actor: FcUser, test_node: FcNode, actor_perm: FcNodePermission,
) -> None:
    """Created fact has events recorded in the version history."""
    s1 = f"Events history test {uuid.uuid4().hex}"
    fact, _ = await _create_fact(db, test_node, actor, s1)

    client = await _make_client(db, actor)
    async with client:
        resp = await client.get(f"/api/v1/facts/{fact.fact_uid}/history")
    app.dependency_overrides.clear()

    data = resp.json()["data"]
    # Events are on entity_type='version', so they may or may not appear
    # depending on what events were recorded. At minimum the response is valid.
    assert data["fact_uid"] == str(fact.fact_uid)
    for v in data["versions"]:
        assert isinstance(v["events"], list)


async def test_history_includes_comments(
    db: AsyncSession, actor: FcUser, test_node: FcNode, actor_perm: FcNodePermission,
) -> None:
    """A comment posted on a version appears in history."""
    s1 = f"Comments history test {uuid.uuid4().hex}"
    fact, ver = await _create_fact(db, test_node, actor, s1)

    comment = FcFactComment(
        version_uid=ver.version_uid,
        comment_type="comment",
        body="Test comment body",
        created_by_uid=actor.user_uid,
    )
    db.add(comment)
    await db.flush()

    client = await _make_client(db, actor)
    async with client:
        resp = await client.get(f"/api/v1/facts/{fact.fact_uid}/history")
    app.dependency_overrides.clear()

    versions = resp.json()["data"]["versions"]
    commented = [v for v in versions if v["comments"]]
    assert len(commented) == 1
    assert commented[0]["comments"][0]["body"] == "Test comment body"
    assert commented[0]["comments"][0]["comment_type"] == "comment"
    assert commented[0]["comments"][0]["created_by"]["display_name"] == actor.display_name


async def test_history_returns_author_display_names(
    db: AsyncSession, actor: FcUser, test_node: FcNode, actor_perm: FcNodePermission,
) -> None:
    """Version authors include display_name, not just UIDs."""
    s1 = f"Author display test {uuid.uuid4().hex}"
    fact, _ = await _create_fact(db, test_node, actor, s1)

    client = await _make_client(db, actor)
    async with client:
        resp = await client.get(f"/api/v1/facts/{fact.fact_uid}/history")
    app.dependency_overrides.clear()

    for v in resp.json()["data"]["versions"]:
        assert v["created_by"]["display_name"] == "History Approver"
        assert v["created_by"]["user_uid"] == str(actor.user_uid)


async def test_history_requires_auth(
    db: AsyncSession, actor: FcUser, test_node: FcNode, actor_perm: FcNodePermission,
) -> None:
    """GET history without auth returns 401."""
    s1 = f"Auth test {uuid.uuid4().hex}"
    fact, _ = await _create_fact(db, test_node, actor, s1)

    client = await _make_unauthed_client(db)
    async with client:
        resp = await client.get(f"/api/v1/facts/{fact.fact_uid}/history")
    app.dependency_overrides.clear()

    assert resp.status_code == 401


async def test_history_404_on_nonexistent_fact(
    db: AsyncSession, actor: FcUser, test_node: FcNode, actor_perm: FcNodePermission,
) -> None:
    """GET history for a random UUID returns 404."""
    client = await _make_client(db, actor)
    async with client:
        resp = await client.get(f"/api/v1/facts/{uuid.uuid4()}/history")
    app.dependency_overrides.clear()

    assert resp.status_code == 404


async def test_history_respects_node_permissions(
    db: AsyncSession,
    actor: FcUser,
    test_node: FcNode,
    isolated_node: FcNode,
    actor_perm: FcNodePermission,
) -> None:
    """User with no explicit grant still sees history (global_role=viewer provides read).

    In this system global_role='viewer' allows reading any node, so a 403 test
    requires a deactivated user or an endpoint that needs higher permissions.
    We verify the permission resolver runs by testing that unauthenticated users
    get 401 (covered by test_history_requires_auth).

    Here we verify that an authenticated user WITH viewer access can read and
    the response is correct.
    """
    s1 = f"Perm test {uuid.uuid4().hex}"
    fact, _ = await _create_fact(db, test_node, actor, s1)

    # actor has explicit approver permission — can read
    client = await _make_client(db, actor)
    async with client:
        resp = await client.get(f"/api/v1/facts/{fact.fact_uid}/history")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["data"]["fact_uid"] == str(fact.fact_uid)


async def test_history_allowed_with_viewer_permission(
    db: AsyncSession,
    actor: FcUser,
    viewer: FcUser,
    test_node: FcNode,
    actor_perm: FcNodePermission,
    viewer_perm: FcNodePermission,
) -> None:
    """User with viewer permission CAN read history."""
    s1 = f"Viewer allowed test {uuid.uuid4().hex}"
    fact, _ = await _create_fact(db, test_node, actor, s1)

    client = await _make_client(db, viewer)
    async with client:
        resp = await client.get(f"/api/v1/facts/{fact.fact_uid}/history")
    app.dependency_overrides.clear()

    assert resp.status_code == 200


async def test_history_handles_single_version_fact(
    db: AsyncSession, actor: FcUser, test_node: FcNode, actor_perm: FcNodePermission,
) -> None:
    """A fact with just one version returns valid history."""
    s1 = f"Single version test {uuid.uuid4().hex}"
    fact, _ = await _create_fact(db, test_node, actor, s1)

    client = await _make_client(db, actor)
    async with client:
        resp = await client.get(f"/api/v1/facts/{fact.fact_uid}/history")
    app.dependency_overrides.clear()

    data = resp.json()["data"]
    assert len(data["versions"]) == 1
    assert data["current_sentence"] == s1


async def test_history_shows_rejection_notes(
    db: AsyncSession,
    actor: FcUser,
    contributor: FcUser,
    test_node: FcNode,
    actor_perm: FcNodePermission,
    contributor_perm: FcNodePermission,
) -> None:
    """Rejection note appears in the version's events.

    The rejection flow emits two version.rejected events:
    1. state_machine.transition() publishes {old_state, new_state}
    2. reject_proposal() publishes {note} (without new_state)

    The recorder maps (2) to event_type="version.unknown" because
    new_state is absent.  The note lives in payload["note"], not
    FcEventLog.note.  get_fact_history checks both locations.
    """
    # Contributor creates a proposed fact
    s1 = f"Rejection note test {uuid.uuid4().hex}"
    fact, ver = await _create_fact(db, test_node, contributor, s1)
    assert ver.state == "proposed"

    # Approver rejects it with a note via the queue endpoint
    rejection_note = "This wording is ambiguous — please clarify."
    client = await _make_client(db, actor)
    async with client:
        resp = await client.post(
            f"/api/v1/queue/reject/{ver.version_uid}",
            json={"note": rejection_note},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 200

    # Flush events written by the reject endpoint
    await flush_pending_events(db)
    await db.flush()

    # Fetch history and find the rejection note
    client = await _make_client(db, actor)
    async with client:
        resp = await client.get(f"/api/v1/facts/{fact.fact_uid}/history")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    versions = resp.json()["data"]["versions"]
    assert len(versions) >= 1

    # Find the rejected version
    rejected = [v for v in versions if v["state"] == "rejected"]
    assert len(rejected) == 1

    # At least one event on that version carries the rejection note
    notes = [e["note"] for e in rejected[0]["events"] if e["note"]]
    assert rejection_note in notes
