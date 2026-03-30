"""Integration tests for challenge creation, approval, and rejection."""

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
from artiFACT.modules.facts.service import create_fact


# ── Fixtures ──


@pytest_asyncio.fixture
async def approver(db: AsyncSession) -> FcUser:
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"ch-approver-{uuid.uuid4().hex[:8]}",
        display_name="Challenge Approver",
        global_role="viewer",
        is_active=True,
        password_hash=hash_password("test2026"),
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def contributor(db: AsyncSession) -> FcUser:
    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"ch-contrib-{uuid.uuid4().hex[:8]}",
        display_name="Challenge Contributor",
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
        title="Challenge Test Root",
        slug=f"ch-root-{uuid.uuid4().hex[:8]}",
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
        title="Challenge Test Node",
        slug=f"ch-node-{uuid.uuid4().hex[:8]}",
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


async def _create_published_fact(
    db: AsyncSession, node: FcNode, actor: FcUser, sentence: str,
) -> tuple[FcFact, FcFactVersion]:
    """Create a fact that auto-publishes (actor is approver)."""
    fact, ver = await create_fact(db, node.node_uid, sentence, actor)
    await flush_pending_events(db)
    await db.flush()
    return fact, ver


# ── Tests: Challenge Creation ──


async def test_create_challenge_via_api(
    db: AsyncSession,
    approver: FcUser,
    contributor: FcUser,
    test_node: FcNode,
    approver_perm: FcNodePermission,
    contributor_perm: FcNodePermission,
) -> None:
    """Contributor can submit a challenge on a published version."""
    sentence = f"Challenge creation test {uuid.uuid4().hex}"
    fact, ver = await _create_published_fact(db, test_node, approver, sentence)
    assert ver.state == "published"

    client = await _make_client(db, contributor)
    async with client:
        resp = await client.post(
            f"/api/v1/facts/{fact.fact_uid}/versions/{ver.version_uid}/comments",
            json={
                "body": "I believe this should be different.",
                "comment_type": "challenge",
                "proposed_sentence": "This is the corrected sentence for testing",
            },
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["comment_type"] == "challenge"
    assert data["proposed_sentence"] == "This is the corrected sentence for testing"
    assert data["resolution_state"] is None


async def test_challenge_requires_proposed_sentence(
    db: AsyncSession,
    approver: FcUser,
    contributor: FcUser,
    test_node: FcNode,
    approver_perm: FcNodePermission,
    contributor_perm: FcNodePermission,
) -> None:
    """Challenge without proposed_sentence returns 409."""
    sentence = f"Missing sentence test {uuid.uuid4().hex}"
    fact, ver = await _create_published_fact(db, test_node, approver, sentence)

    client = await _make_client(db, contributor)
    async with client:
        resp = await client.post(
            f"/api/v1/facts/{fact.fact_uid}/versions/{ver.version_uid}/comments",
            json={
                "body": "This is wrong.",
                "comment_type": "challenge",
            },
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 409


async def test_challenge_on_proposed_version(
    db: AsyncSession,
    contributor: FcUser,
    test_node: FcNode,
    contributor_perm: FcNodePermission,
) -> None:
    """Challenge on a proposed version is allowed."""
    sentence = f"Proposed challenge test {uuid.uuid4().hex}"
    fact, ver = await create_fact(db, test_node.node_uid, sentence, contributor)
    await flush_pending_events(db)
    await db.flush()
    assert ver.state == "proposed"

    client = await _make_client(db, contributor)
    async with client:
        resp = await client.post(
            f"/api/v1/facts/{fact.fact_uid}/versions/{ver.version_uid}/comments",
            json={
                "body": "I think this should be worded differently.",
                "comment_type": "challenge",
                "proposed_sentence": "Alternative wording for proposed version",
            },
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 201


# ── Tests: Challenge Approval ──


async def test_approve_challenge_creates_new_version(
    db: AsyncSession,
    approver: FcUser,
    contributor: FcUser,
    test_node: FcNode,
    approver_perm: FcNodePermission,
    contributor_perm: FcNodePermission,
) -> None:
    """Approving a challenge creates a new published version with the proposed sentence."""
    sentence = f"Approve challenge test {uuid.uuid4().hex}"
    fact, ver = await _create_published_fact(db, test_node, approver, sentence)
    proposed = f"Better wording {uuid.uuid4().hex}"

    # Contributor creates challenge
    from artiFACT.modules.facts.history import add_comment

    comment = await add_comment(
        db, fact.fact_uid, ver.version_uid,
        "This wording is wrong.", "challenge", None, contributor,
        proposed_sentence=proposed,
    )
    await flush_pending_events(db)
    await db.flush()

    # Approver approves via API
    client = await _make_client(db, approver)
    async with client:
        resp = await client.post(
            f"/api/v1/queue/approve-challenge/{comment.comment_uid}",
            json={"note": "Good catch."},
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["status"] == "challenge_approved"

    # Verify comment is resolved
    await db.refresh(comment)
    assert comment.resolution_state == "approved"
    assert comment.resolved_by_uid == approver.user_uid
    assert comment.resolved_at is not None

    # Verify new version was created
    await db.refresh(fact)
    new_ver = await db.get(FcFactVersion, fact.current_published_version_uid)
    assert new_ver is not None
    assert new_ver.display_sentence == proposed
    assert new_ver.state == "published"
    assert new_ver.supersedes_version_uid == ver.version_uid


# ── Tests: Challenge Rejection ──


async def test_reject_challenge_with_note(
    db: AsyncSession,
    approver: FcUser,
    contributor: FcUser,
    test_node: FcNode,
    approver_perm: FcNodePermission,
    contributor_perm: FcNodePermission,
) -> None:
    """Rejecting a challenge sets resolution_state and note without creating a new version."""
    sentence = f"Reject challenge test {uuid.uuid4().hex}"
    fact, ver = await _create_published_fact(db, test_node, approver, sentence)

    from artiFACT.modules.facts.history import add_comment

    comment = await add_comment(
        db, fact.fact_uid, ver.version_uid,
        "I think this is wrong.", "challenge", None, contributor,
        proposed_sentence="Rejected wording for test purposes",
    )
    await flush_pending_events(db)
    await db.flush()

    rejection_note = "The current wording is correct per official docs."
    client = await _make_client(db, approver)
    async with client:
        resp = await client.post(
            f"/api/v1/queue/reject-challenge/{comment.comment_uid}",
            json={"note": rejection_note},
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["status"] == "challenge_rejected"

    await db.refresh(comment)
    assert comment.resolution_state == "rejected"
    assert comment.resolution_note == rejection_note
    assert comment.resolved_by_uid == approver.user_uid

    # Fact still points to the original version
    await db.refresh(fact)
    assert fact.current_published_version_uid == ver.version_uid


async def test_cannot_resolve_already_resolved_challenge(
    db: AsyncSession,
    approver: FcUser,
    contributor: FcUser,
    test_node: FcNode,
    approver_perm: FcNodePermission,
    contributor_perm: FcNodePermission,
) -> None:
    """Double-resolving a challenge returns 409."""
    sentence = f"Double resolve test {uuid.uuid4().hex}"
    fact, ver = await _create_published_fact(db, test_node, approver, sentence)

    from artiFACT.modules.facts.history import add_comment

    comment = await add_comment(
        db, fact.fact_uid, ver.version_uid,
        "Challenge this.", "challenge", None, contributor,
        proposed_sentence="Double resolve proposed sentence text",
    )
    await flush_pending_events(db)
    await db.flush()

    # First rejection succeeds
    client = await _make_client(db, approver)
    async with client:
        resp1 = await client.post(
            f"/api/v1/queue/reject-challenge/{comment.comment_uid}",
            json={},
        )
        # Second attempt on same challenge fails
        resp2 = await client.post(
            f"/api/v1/queue/reject-challenge/{comment.comment_uid}",
            json={},
        )
    app.dependency_overrides.clear()

    assert resp1.status_code == 200
    assert resp2.status_code == 409


# ── Tests: Queue Endpoints ──


async def test_pending_challenges_appear_in_queue(
    db: AsyncSession,
    approver: FcUser,
    contributor: FcUser,
    test_node: FcNode,
    approver_perm: FcNodePermission,
    contributor_perm: FcNodePermission,
) -> None:
    """Pending challenges show up in GET /api/v1/queue/challenges."""
    sentence = f"Queue challenge test {uuid.uuid4().hex}"
    fact, ver = await _create_published_fact(db, test_node, approver, sentence)

    from artiFACT.modules.facts.history import add_comment

    await add_comment(
        db, fact.fact_uid, ver.version_uid,
        "Needs fixing.", "challenge", None, contributor,
        proposed_sentence="Queue test proposed sentence wording",
    )
    await flush_pending_events(db)
    await db.flush()

    client = await _make_client(db, approver)
    async with client:
        resp = await client.get("/api/v1/queue/challenges")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    challenge = data["data"][0]
    assert challenge["proposed_sentence"] == "Queue test proposed sentence wording"
    assert challenge["node_title"] == "Challenge Test Node"


async def test_my_challenges_shows_submitter_view(
    db: AsyncSession,
    approver: FcUser,
    contributor: FcUser,
    test_node: FcNode,
    approver_perm: FcNodePermission,
    contributor_perm: FcNodePermission,
) -> None:
    """GET /api/v1/queue/my-challenges shows challenges submitted by the current user."""
    sentence = f"My challenges test {uuid.uuid4().hex}"
    fact, ver = await _create_published_fact(db, test_node, approver, sentence)

    from artiFACT.modules.facts.history import add_comment

    await add_comment(
        db, fact.fact_uid, ver.version_uid,
        "I think this is wrong.", "challenge", None, contributor,
        proposed_sentence="My challenges proposed sentence text",
    )
    await flush_pending_events(db)
    await db.flush()

    # Contributor sees their own challenge
    client = await _make_client(db, contributor)
    async with client:
        resp = await client.get("/api/v1/queue/my-challenges")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["data"][0]["proposed_sentence"] == "My challenges proposed sentence text"
    assert data["data"][0]["resolution_state"] is None


async def test_badge_count_includes_challenges(
    db: AsyncSession,
    approver: FcUser,
    contributor: FcUser,
    test_node: FcNode,
    approver_perm: FcNodePermission,
    contributor_perm: FcNodePermission,
) -> None:
    """GET /api/v1/queue/counts includes challenge count."""
    sentence = f"Badge count test {uuid.uuid4().hex}"
    fact, ver = await _create_published_fact(db, test_node, approver, sentence)

    from artiFACT.modules.facts.history import add_comment

    await add_comment(
        db, fact.fact_uid, ver.version_uid,
        "Badge test challenge.", "challenge", None, contributor,
        proposed_sentence="Badge count proposed sentence text here",
    )
    await flush_pending_events(db)
    await db.flush()

    client = await _make_client(db, approver)
    async with client:
        resp = await client.get("/api/v1/queue/counts")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["challenges"] >= 1
    assert data["total"] >= 1


async def test_challenge_shows_in_fact_history(
    db: AsyncSession,
    approver: FcUser,
    contributor: FcUser,
    test_node: FcNode,
    approver_perm: FcNodePermission,
    contributor_perm: FcNodePermission,
) -> None:
    """A challenge appears in the fact history with proposed_sentence and resolution fields."""
    sentence = f"History challenge test {uuid.uuid4().hex}"
    fact, ver = await _create_published_fact(db, test_node, approver, sentence)

    from artiFACT.modules.facts.history import add_comment

    await add_comment(
        db, fact.fact_uid, ver.version_uid,
        "This needs correction.", "challenge", None, contributor,
        proposed_sentence="History challenge proposed alternative",
    )
    await flush_pending_events(db)
    await db.flush()

    client = await _make_client(db, approver)
    async with client:
        resp = await client.get(f"/api/v1/facts/{fact.fact_uid}/history")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    versions = resp.json()["data"]["versions"]
    published = [v for v in versions if v["state"] == "published"]
    assert len(published) == 1
    challenges = [c for c in published[0]["comments"] if c["comment_type"] == "challenge"]
    assert len(challenges) == 1
    assert challenges[0]["proposed_sentence"] == "History challenge proposed alternative"
    assert challenges[0]["resolution_state"] is None


async def test_scope_enforcement_on_challenge_approve(
    db: AsyncSession,
    contributor: FcUser,
    approver: FcUser,
    test_node: FcNode,
    approver_perm: FcNodePermission,
    contributor_perm: FcNodePermission,
) -> None:
    """Contributor cannot approve a challenge (lacks approver scope)."""
    sentence = f"Scope test {uuid.uuid4().hex}"
    fact, ver = await _create_published_fact(db, test_node, approver, sentence)

    from artiFACT.modules.facts.history import add_comment

    comment = await add_comment(
        db, fact.fact_uid, ver.version_uid,
        "Scope challenge.", "challenge", None, contributor,
        proposed_sentence="Scope enforcement proposed sentence text",
    )
    await flush_pending_events(db)
    await db.flush()

    # Contributor tries to approve — should fail
    client = await _make_client(db, contributor)
    async with client:
        resp = await client.post(
            f"/api/v1/queue/approve-challenge/{comment.comment_uid}",
            json={},
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 403
