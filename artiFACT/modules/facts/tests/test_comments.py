"""Integration tests for fact comment endpoints."""

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.csrf import generate_csrf_token
from artiFACT.kernel.auth.session import create_session
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import (
    FcEventLog,
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
async def approver(db: AsyncSession) -> FcUser:
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"comment-approver-{uuid.uuid4().hex[:8]}",
        display_name="Comment Approver",
        global_role="viewer",
        is_active=True,
        password_hash=hash_password("test2026"),
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def contrib(db: AsyncSession) -> FcUser:
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"comment-contrib-{uuid.uuid4().hex[:8]}",
        display_name="Comment Contributor",
        global_role="viewer",
        is_active=True,
        password_hash=hash_password("test2026"),
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def viewer(db: AsyncSession) -> FcUser:
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"comment-viewer-{uuid.uuid4().hex[:8]}",
        display_name="Comment Viewer",
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
        title="Comment Test Root",
        slug=f"cmt-root-{uuid.uuid4().hex[:8]}",
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
        title="Comment Test Node",
        slug=f"cmt-node-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


@pytest_asyncio.fixture
async def approver_perm(
    db: AsyncSession, approver: FcUser, test_node: FcNode, admin_user: FcUser,
) -> FcNodePermission:
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=approver.user_uid,
        node_uid=test_node.node_uid,
        role="approver",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()
    return perm


@pytest_asyncio.fixture
async def contrib_perm(
    db: AsyncSession, contrib: FcUser, test_node: FcNode, admin_user: FcUser,
) -> FcNodePermission:
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=contrib.user_uid,
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


@pytest_asyncio.fixture
async def fact_with_version(
    db: AsyncSession, approver: FcUser, test_node: FcNode, approver_perm: FcNodePermission,
) -> tuple[FcFact, FcFactVersion]:
    """Create a fact with one published version."""
    sentence = f"Comment test fact {uuid.uuid4().hex}"
    fact, ver = await create_fact(db, test_node.node_uid, sentence, approver)
    await flush_pending_events(db)
    await db.flush()
    return fact, ver


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


def _comment_url(fact_uid: uuid.UUID, version_uid: uuid.UUID) -> str:
    return f"/api/v1/facts/{fact_uid}/versions/{version_uid}/comments"


# ── Tests ──


async def test_create_comment_success(
    db: AsyncSession,
    approver: FcUser,
    fact_with_version: tuple[FcFact, FcFactVersion],
) -> None:
    """POST comment returns 201 with correct fields."""
    fact, ver = fact_with_version
    client = await _make_client(db, approver)
    async with client:
        resp = await client.post(
            _comment_url(fact.fact_uid, ver.version_uid),
            json={"body": "This looks correct.", "comment_type": "comment"},
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert "comment_uid" in data
    assert data["body"] == "This looks correct."
    assert data["comment_type"] == "comment"
    assert data["created_by"]["display_name"] == "Comment Approver"

    # Verify persisted
    result = await db.execute(
        select(FcFactComment).where(FcFactComment.comment_uid == data["comment_uid"])
    )
    row = result.scalar_one()
    assert row.body == "This looks correct."


async def test_create_comment_emits_event(
    db: AsyncSession,
    approver: FcUser,
    fact_with_version: tuple[FcFact, FcFactVersion],
) -> None:
    """Posting a comment writes a comment.created event to fc_event_log."""
    fact, ver = fact_with_version
    client = await _make_client(db, approver)
    async with client:
        resp = await client.post(
            _comment_url(fact.fact_uid, ver.version_uid),
            json={"body": "Event test comment", "comment_type": "comment"},
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 201
    comment_uid = resp.json()["data"]["comment_uid"]

    result = await db.execute(
        select(FcEventLog).where(
            FcEventLog.entity_type == "comment",
            FcEventLog.entity_uid == comment_uid,
            FcEventLog.event_type == "comment.created",
        )
    )
    events = result.scalars().all()
    assert len(events) >= 1
    assert events[0].actor_uid == approver.user_uid


async def test_create_challenge_comment(
    db: AsyncSession,
    approver: FcUser,
    fact_with_version: tuple[FcFact, FcFactVersion],
) -> None:
    """Challenge comment type is accepted and persisted."""
    fact, ver = fact_with_version
    client = await _make_client(db, approver)
    async with client:
        resp = await client.post(
            _comment_url(fact.fact_uid, ver.version_uid),
            json={
                "body": "I dispute this.",
                "comment_type": "challenge",
                "proposed_sentence": "The revised wording that I propose instead.",
            },
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 201
    assert resp.json()["data"]["comment_type"] == "challenge"


async def test_create_resolution_comment(
    db: AsyncSession,
    approver: FcUser,
    fact_with_version: tuple[FcFact, FcFactVersion],
) -> None:
    """Resolution comment type is accepted."""
    fact, ver = fact_with_version
    client = await _make_client(db, approver)
    async with client:
        resp = await client.post(
            _comment_url(fact.fact_uid, ver.version_uid),
            json={"body": "Resolved per review.", "comment_type": "resolution"},
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 201
    assert resp.json()["data"]["comment_type"] == "resolution"


async def test_comment_requires_auth(
    db: AsyncSession,
    fact_with_version: tuple[FcFact, FcFactVersion],
) -> None:
    """POST without auth is blocked before reaching the handler.

    The middleware stack is: SecurityHeaders → RequestID → CSRF → App.
    An unauthenticated POST has no csrf_token cookie, so the CSRF
    middleware rejects it with 403 "CSRF token missing" before the
    auth dependency can return 401. This is consistent across all
    non-CSRF-exempt POST endpoints in the app. The request is blocked
    either way — we accept both codes to document this ordering.
    """
    fact, ver = fact_with_version
    client = await _make_unauthed_client(db)
    async with client:
        resp = await client.post(
            _comment_url(fact.fact_uid, ver.version_uid),
            json={"body": "no auth", "comment_type": "comment"},
        )
    app.dependency_overrides.clear()

    assert resp.status_code in (401, 403)


async def test_comment_requires_csrf(
    db: AsyncSession,
    approver: FcUser,
    fact_with_version: tuple[FcFact, FcFactVersion],
) -> None:
    """POST without CSRF token returns 403."""
    fact, ver = fact_with_version
    client = await _make_client(db, approver, with_csrf=False)
    async with client:
        resp = await client.post(
            _comment_url(fact.fact_uid, ver.version_uid),
            json={"body": "no csrf", "comment_type": "comment"},
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 403
    assert "CSRF" in resp.text


async def test_comment_requires_contributor_permission(
    db: AsyncSession,
    viewer: FcUser,
    contrib: FcUser,
    viewer_perm: FcNodePermission,
    contrib_perm: FcNodePermission,
    fact_with_version: tuple[FcFact, FcFactVersion],
) -> None:
    """Viewer-only user gets 403; contributor succeeds."""
    fact, ver = fact_with_version

    # Viewer → 403
    client = await _make_client(db, viewer)
    async with client:
        resp = await client.post(
            _comment_url(fact.fact_uid, ver.version_uid),
            json={"body": "viewer trying", "comment_type": "comment"},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 403

    # Contributor → 201
    client = await _make_client(db, contrib)
    async with client:
        resp = await client.post(
            _comment_url(fact.fact_uid, ver.version_uid),
            json={"body": "contributor comment", "comment_type": "comment"},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 201


async def test_comment_rejects_empty_body(
    db: AsyncSession,
    approver: FcUser,
    fact_with_version: tuple[FcFact, FcFactVersion],
) -> None:
    """Empty body or whitespace-only body is rejected."""
    fact, ver = fact_with_version
    client = await _make_client(db, approver)
    async with client:
        resp1 = await client.post(
            _comment_url(fact.fact_uid, ver.version_uid),
            json={"body": "", "comment_type": "comment"},
        )
        resp2 = await client.post(
            _comment_url(fact.fact_uid, ver.version_uid),
            json={"body": "   ", "comment_type": "comment"},
        )
    app.dependency_overrides.clear()

    assert resp1.status_code == 422
    # Whitespace-only gets past Pydantic min_length but caught by service
    assert resp2.status_code in (409, 422)


async def test_comment_rejects_invalid_comment_type(
    db: AsyncSession,
    approver: FcUser,
    fact_with_version: tuple[FcFact, FcFactVersion],
) -> None:
    """Invalid comment_type is rejected with 422."""
    fact, ver = fact_with_version
    client = await _make_client(db, approver)
    async with client:
        resp = await client.post(
            _comment_url(fact.fact_uid, ver.version_uid),
            json={"body": "test", "comment_type": "invalid_type"},
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 422


async def test_comment_404_on_wrong_fact(
    db: AsyncSession,
    approver: FcUser,
    approver_perm: FcNodePermission,
    test_node: FcNode,
    fact_with_version: tuple[FcFact, FcFactVersion],
) -> None:
    """Version belonging to a different fact returns 404."""
    fact_a, ver_a = fact_with_version

    # Create fact B
    s2 = f"Fact B for wrong-fact test {uuid.uuid4().hex}"
    fact_b, ver_b = await create_fact(db, test_node.node_uid, s2, approver)
    await flush_pending_events(db)
    await db.flush()

    # POST to fact_A with version_B
    client = await _make_client(db, approver)
    async with client:
        resp = await client.post(
            _comment_url(fact_a.fact_uid, ver_b.version_uid),
            json={"body": "wrong fact", "comment_type": "comment"},
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 404


async def test_comment_404_on_nonexistent_version(
    db: AsyncSession,
    approver: FcUser,
    fact_with_version: tuple[FcFact, FcFactVersion],
) -> None:
    """Random version UUID returns 404."""
    fact, _ = fact_with_version
    client = await _make_client(db, approver)
    async with client:
        resp = await client.post(
            _comment_url(fact.fact_uid, uuid.uuid4()),
            json={"body": "no version", "comment_type": "comment"},
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 404


async def test_threaded_reply_comment(
    db: AsyncSession,
    approver: FcUser,
    fact_with_version: tuple[FcFact, FcFactVersion],
) -> None:
    """A reply referencing parent_comment_uid succeeds."""
    fact, ver = fact_with_version

    client = await _make_client(db, approver)
    async with client:
        # Create parent comment
        resp1 = await client.post(
            _comment_url(fact.fact_uid, ver.version_uid),
            json={"body": "Parent comment", "comment_type": "comment"},
        )
        assert resp1.status_code == 201
        parent_uid = resp1.json()["data"]["comment_uid"]

        # Create reply
        resp2 = await client.post(
            _comment_url(fact.fact_uid, ver.version_uid),
            json={
                "body": "Reply to parent",
                "comment_type": "comment",
                "parent_comment_uid": parent_uid,
            },
        )
    app.dependency_overrides.clear()

    assert resp2.status_code == 201
    assert resp2.json()["data"]["parent_comment_uid"] == parent_uid

    # Verify in history
    client = await _make_client(db, approver)
    async with client:
        resp3 = await client.get(f"/api/v1/facts/{fact.fact_uid}/history")
    app.dependency_overrides.clear()

    comments = resp3.json()["data"]["versions"][0]["comments"]
    assert len(comments) == 2
    reply = [c for c in comments if c["parent_comment_uid"] == parent_uid]
    assert len(reply) == 1


async def test_threaded_reply_wrong_version_rejected(
    db: AsyncSession,
    approver: FcUser,
    approver_perm: FcNodePermission,
    test_node: FcNode,
    fact_with_version: tuple[FcFact, FcFactVersion],
) -> None:
    """Parent comment on V1, reply on V2 → 409 conflict."""
    fact, ver1 = fact_with_version

    # Create a comment on ver1
    comment = FcFactComment(
        version_uid=ver1.version_uid,
        comment_type="comment",
        body="V1 comment",
        created_by_uid=approver.user_uid,
    )
    db.add(comment)
    await db.flush()

    # Edit fact to create ver2
    s2 = f"Edited for thread test {uuid.uuid4().hex}"
    _, ver2 = await edit_fact(db, fact.fact_uid, s2, approver)
    await flush_pending_events(db)
    await db.flush()

    # Try to reply on ver2 with parent from ver1
    client = await _make_client(db, approver)
    async with client:
        resp = await client.post(
            _comment_url(fact.fact_uid, ver2.version_uid),
            json={
                "body": "Cross-version reply",
                "comment_type": "comment",
                "parent_comment_uid": str(comment.comment_uid),
            },
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 409
