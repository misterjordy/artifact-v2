"""Tests for auto-approve toggle and drag-and-drop move backend."""

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.csrf import generate_csrf_token
from artiFACT.kernel.auth.session import (
    create_session,
    get_session_data,
    is_auto_approve_active,
    update_session_field,
)
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import (
    FcEventLog,
    FcFact,
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
        cac_dn=f"mv-approver-{uuid.uuid4().hex[:8]}",
        display_name="Move Approver",
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
        cac_dn=f"mv-contrib-{uuid.uuid4().hex[:8]}",
        display_name="Move Contributor",
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
        title="Move Test Root",
        slug=f"mv-root-{uuid.uuid4().hex[:8]}",
        node_depth=0,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


@pytest_asyncio.fixture
async def source_node(db: AsyncSession, test_root: FcNode, admin_user: FcUser) -> FcNode:
    node = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=test_root.node_uid,
        title="Source Node",
        slug=f"source-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


@pytest_asyncio.fixture
async def target_node(db: AsyncSession, test_root: FcNode, admin_user: FcUser) -> FcNode:
    node = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=test_root.node_uid,
        title="Target Node",
        slug=f"target-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


@pytest_asyncio.fixture
async def child_of_source(
    db: AsyncSession, source_node: FcNode, admin_user: FcUser,
) -> FcNode:
    node = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=source_node.node_uid,
        title="Child of Source",
        slug=f"child-src-{uuid.uuid4().hex[:8]}",
        node_depth=2,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


@pytest_asyncio.fixture
async def approver_source_perm(
    db: AsyncSession, approver: FcUser, source_node: FcNode, admin_user: FcUser,
) -> FcNodePermission:
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=approver.user_uid,
        node_uid=source_node.node_uid,
        role="approver",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()
    return perm


@pytest_asyncio.fixture
async def approver_target_perm(
    db: AsyncSession, approver: FcUser, target_node: FcNode, admin_user: FcUser,
) -> FcNodePermission:
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=approver.user_uid,
        node_uid=target_node.node_uid,
        role="approver",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()
    return perm


@pytest_asyncio.fixture
async def contrib_source_perm(
    db: AsyncSession, contributor: FcUser, source_node: FcNode, admin_user: FcUser,
) -> FcNodePermission:
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=contributor.user_uid,
        node_uid=source_node.node_uid,
        role="contributor",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()
    return perm


@pytest_asyncio.fixture
async def contrib_target_perm(
    db: AsyncSession, contributor: FcUser, target_node: FcNode, admin_user: FcUser,
) -> FcNodePermission:
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=contributor.user_uid,
        node_uid=target_node.node_uid,
        role="contributor",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()
    return perm


async def _make_client(
    db: AsyncSession, user: FcUser, *, with_csrf: bool = True,
    auto_approve: bool = False,
) -> tuple[AsyncClient, str]:
    """Create test client. Returns (client, session_id) for session manipulation."""
    session_id = await create_session(user)
    if auto_approve:
        await update_session_field(session_id, "auto_approve", True)
    csrf_token = generate_csrf_token()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    cookies = {"session_id": session_id, "csrf_token": csrf_token}
    headers = {"x-csrf-token": csrf_token} if with_csrf else {}
    client = AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies=cookies,
        headers=headers,
    )
    return client, session_id


async def _create_fact_in_node(
    db: AsyncSession, node: FcNode, actor: FcUser,
    *, auto_approve: bool = False,
) -> tuple[FcFact, FcFactVersion]:
    """Helper to create a fact in a node."""
    sentence = f"Test fact {uuid.uuid4().hex[:12]}"
    fact, ver = await create_fact(
        db, node.node_uid, sentence, actor,
        auto_approve=auto_approve,
    )
    await flush_pending_events(db)
    await db.flush()
    return fact, ver


# ════════════════════════════════════════════════════
# AUTO-APPROVE TOGGLE TESTS
# ════════════════════════════════════════════════════


async def test_auto_approve_status_default_off(
    db: AsyncSession, approver: FcUser, source_node: FcNode,
    approver_source_perm: FcNodePermission,
) -> None:
    """GET /auto-approve/status default active=false."""
    client, _ = await _make_client(db, approver)
    async with client:
        resp = await client.get("/api/v1/auto-approve/status")
    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is False
    assert data["eligible"] is True


async def test_auto_approve_toggle_on_for_eligible_user(
    db: AsyncSession, approver: FcUser, source_node: FcNode,
    approver_source_perm: FcNodePermission,
) -> None:
    """Eligible user can toggle auto-approve on."""
    client, _ = await _make_client(db, approver)
    async with client:
        resp = await client.post(
            "/api/v1/auto-approve/toggle", json={"active": True},
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is True

        # Verify status endpoint reflects the change
        status = await client.get("/api/v1/auto-approve/status")
        assert status.json()["active"] is True
    app.dependency_overrides.clear()


async def test_auto_approve_toggle_rejected_for_ineligible_user(
    db: AsyncSession, contributor: FcUser,
    contrib_source_perm: FcNodePermission,
) -> None:
    """Contributor cannot toggle auto-approve on (no approve scope)."""
    client, _ = await _make_client(db, contributor)
    async with client:
        resp = await client.post(
            "/api/v1/auto-approve/toggle", json={"active": True},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 403


async def test_auto_approve_is_session_only(
    db: AsyncSession, approver: FcUser, source_node: FcNode,
    approver_source_perm: FcNodePermission,
) -> None:
    """Toggle on in session A. New session B has active=false."""
    # Session A: toggle ON
    client_a, sid_a = await _make_client(db, approver)
    async with client_a:
        resp = await client_a.post(
            "/api/v1/auto-approve/toggle", json={"active": True},
        )
        assert resp.json()["active"] is True
    app.dependency_overrides.clear()

    # Session B: fresh session, should be OFF
    client_b, sid_b = await _make_client(db, approver)
    async with client_b:
        status = await client_b.get("/api/v1/auto-approve/status")
    app.dependency_overrides.clear()
    assert status.json()["active"] is False
    assert sid_a != sid_b


# ════════════════════════════════════════════════════
# VERSIONING BEHAVIOR CHANGE TESTS
# ════════════════════════════════════════════════════


async def test_approver_creates_proposed_when_toggle_off(
    db: AsyncSession, approver: FcUser, source_node: FcNode,
    approver_source_perm: FcNodePermission,
) -> None:
    """KEY CHANGE: approver with toggle OFF creates proposed, not published."""
    fact, ver = await _create_fact_in_node(db, source_node, approver, auto_approve=False)
    assert ver.state == "proposed"
    assert ver.published_at is None


async def test_approver_creates_published_when_toggle_on(
    db: AsyncSession, approver: FcUser, source_node: FcNode,
    approver_source_perm: FcNodePermission,
) -> None:
    """Approver with toggle ON creates published."""
    fact, ver = await _create_fact_in_node(db, source_node, approver, auto_approve=True)
    assert ver.state == "published"
    assert ver.published_at is not None
    assert fact.current_published_version_uid == ver.version_uid


async def test_contributor_always_creates_proposed_regardless_of_toggle(
    db: AsyncSession, contributor: FcUser, source_node: FcNode,
    contrib_source_perm: FcNodePermission,
) -> None:
    """Toggle ON has no effect without approve permission."""
    fact, ver = await _create_fact_in_node(db, source_node, contributor, auto_approve=True)
    assert ver.state == "proposed"


async def test_approver_edit_proposed_when_toggle_off(
    db: AsyncSession, approver: FcUser, source_node: FcNode,
    approver_source_perm: FcNodePermission,
) -> None:
    """Approver edit with toggle OFF creates proposed version."""
    fact, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)
    _, new_ver = await edit_fact(
        db, fact.fact_uid, f"Edited fact {uuid.uuid4().hex[:8]}", approver,
        auto_approve=False,
    )
    await flush_pending_events(db)
    await db.flush()
    assert new_ver.state == "proposed"


async def test_approver_edit_published_when_toggle_on(
    db: AsyncSession, approver: FcUser, source_node: FcNode,
    approver_source_perm: FcNodePermission,
) -> None:
    """Approver edit with toggle ON creates published version."""
    fact, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)
    _, new_ver = await edit_fact(
        db, fact.fact_uid, f"Edited fact {uuid.uuid4().hex[:8]}", approver,
        auto_approve=True,
    )
    await flush_pending_events(db)
    await db.flush()
    assert new_ver.state == "published"
    assert new_ver.published_at is not None


async def test_queue_approve_still_works_regardless_of_toggle(
    db: AsyncSession, approver: FcUser, contributor: FcUser,
    source_node: FcNode,
    approver_source_perm: FcNodePermission,
    contrib_source_perm: FcNodePermission,
) -> None:
    """Explicit queue approve works even when toggle is OFF."""
    # Contributor creates proposed fact
    fact, ver = await _create_fact_in_node(db, source_node, contributor)
    assert ver.state == "proposed"

    # Approver approves via queue (toggle is OFF, doesn't matter)
    client, _ = await _make_client(db, approver, auto_approve=False)
    async with client:
        resp = await client.post(
            f"/api/v1/queue/approve/{ver.version_uid}", json={},
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    await db.refresh(ver)
    assert ver.state == "published"


# ════════════════════════════════════════════════════
# FACT MOVE TESTS
# ════════════════════════════════════════════════════


async def test_propose_fact_move_success(
    db: AsyncSession, contributor: FcUser, approver: FcUser,
    source_node: FcNode, target_node: FcNode,
    approver_source_perm: FcNodePermission,
    contrib_source_perm: FcNodePermission,
    contrib_target_perm: FcNodePermission,
) -> None:
    """Contributor can propose moving a fact."""
    fact, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)

    client, _ = await _make_client(db, contributor)
    async with client:
        resp = await client.post("/api/v1/moves/fact", json={
            "fact_uid": str(fact.fact_uid),
            "target_node_uid": str(target_node.node_uid),
            "comment": "Moving for better organization",
        })
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["status"] == "proposed"
    assert resp.json()["event_uid"] is not None


async def test_propose_fact_move_rejects_same_node(
    db: AsyncSession, contributor: FcUser, approver: FcUser,
    source_node: FcNode,
    approver_source_perm: FcNodePermission,
    contrib_source_perm: FcNodePermission,
) -> None:
    """Moving to the same node returns 409."""
    fact, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)

    client, _ = await _make_client(db, contributor)
    async with client:
        resp = await client.post("/api/v1/moves/fact", json={
            "fact_uid": str(fact.fact_uid),
            "target_node_uid": str(source_node.node_uid),
            "comment": "Same node move",
        })
    app.dependency_overrides.clear()

    assert resp.status_code == 409


async def test_propose_fact_move_requires_contribute_on_both_nodes(
    db: AsyncSession, contributor: FcUser, approver: FcUser,
    source_node: FcNode, target_node: FcNode,
    approver_source_perm: FcNodePermission,
    contrib_source_perm: FcNodePermission,
    # Note: no contrib_target_perm — contributor has no access to target
) -> None:
    """403 when contributor lacks permission on target."""
    fact, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)

    client, _ = await _make_client(db, contributor)
    async with client:
        resp = await client.post("/api/v1/moves/fact", json={
            "fact_uid": str(fact.fact_uid),
            "target_node_uid": str(target_node.node_uid),
            "comment": "No access to target",
        })
    app.dependency_overrides.clear()

    assert resp.status_code == 403


async def test_approve_fact_move_executes_move(
    db: AsyncSession, contributor: FcUser, approver: FcUser,
    source_node: FcNode, target_node: FcNode,
    approver_source_perm: FcNodePermission,
    approver_target_perm: FcNodePermission,
    contrib_source_perm: FcNodePermission,
    contrib_target_perm: FcNodePermission,
) -> None:
    """Approving a fact move changes fact.node_uid."""
    fact, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)

    # Contributor proposes
    client_c, _ = await _make_client(db, contributor)
    async with client_c:
        resp = await client_c.post("/api/v1/moves/fact", json={
            "fact_uid": str(fact.fact_uid),
            "target_node_uid": str(target_node.node_uid),
            "comment": "Move for approval test",
        })
    app.dependency_overrides.clear()
    event_uid = resp.json()["event_uid"]

    # Approver approves
    client_a, _ = await _make_client(db, approver)
    async with client_a:
        resp = await client_a.post(f"/api/v1/moves/{event_uid}/approve")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    await db.refresh(fact)
    assert fact.node_uid == target_node.node_uid


async def test_approve_move_requires_approve_permission(
    db: AsyncSession, contributor: FcUser, approver: FcUser,
    source_node: FcNode, target_node: FcNode,
    approver_source_perm: FcNodePermission,
    contrib_source_perm: FcNodePermission,
    contrib_target_perm: FcNodePermission,
) -> None:
    """Contributor cannot approve a move (lacks approve scope)."""
    fact, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)

    client_c, _ = await _make_client(db, contributor)
    async with client_c:
        resp = await client_c.post("/api/v1/moves/fact", json={
            "fact_uid": str(fact.fact_uid),
            "target_node_uid": str(target_node.node_uid),
            "comment": "Test",
        })
    app.dependency_overrides.clear()
    event_uid = resp.json()["event_uid"]

    # Contributor tries to approve — should fail
    client_c2, _ = await _make_client(db, contributor)
    async with client_c2:
        resp = await client_c2.post(f"/api/v1/moves/{event_uid}/approve")
    app.dependency_overrides.clear()

    assert resp.status_code == 403


async def test_reject_fact_move_preserves_location(
    db: AsyncSession, contributor: FcUser, approver: FcUser,
    source_node: FcNode, target_node: FcNode,
    approver_source_perm: FcNodePermission,
    approver_target_perm: FcNodePermission,
    contrib_source_perm: FcNodePermission,
    contrib_target_perm: FcNodePermission,
) -> None:
    """Rejecting a move keeps fact in its original node."""
    fact, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)
    original_node = fact.node_uid

    client_c, _ = await _make_client(db, contributor)
    async with client_c:
        resp = await client_c.post("/api/v1/moves/fact", json={
            "fact_uid": str(fact.fact_uid),
            "target_node_uid": str(target_node.node_uid),
            "comment": "Will be rejected",
        })
    app.dependency_overrides.clear()
    event_uid = resp.json()["event_uid"]

    client_a, _ = await _make_client(db, approver)
    async with client_a:
        resp = await client_a.post(
            f"/api/v1/moves/{event_uid}/reject", json={"note": "Not needed"},
        )
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    await db.refresh(fact)
    assert fact.node_uid == original_node


async def test_auto_approve_fact_move_skips_queue(
    db: AsyncSession, approver: FcUser,
    source_node: FcNode, target_node: FcNode,
    approver_source_perm: FcNodePermission,
    approver_target_perm: FcNodePermission,
) -> None:
    """Auto-approve move goes straight to moved status."""
    fact, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)

    client, _ = await _make_client(db, approver, auto_approve=True)
    async with client:
        resp = await client.post("/api/v1/moves/fact", json={
            "fact_uid": str(fact.fact_uid),
            "target_node_uid": str(target_node.node_uid),
            "comment": "Auto approve move",
            "auto_approve": True,
        })
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["status"] == "moved"
    await db.refresh(fact)
    assert fact.node_uid == target_node.node_uid


async def test_auto_approve_without_approve_perm_falls_back_to_proposed(
    db: AsyncSession, contributor: FcUser,
    source_node: FcNode, target_node: FcNode,
    contrib_source_perm: FcNodePermission,
    contrib_target_perm: FcNodePermission,
) -> None:
    """auto_approve=True but no approve perm → still proposed."""
    fact, _ = await _create_fact_in_node(db, source_node, contributor)

    client, _ = await _make_client(db, contributor, auto_approve=True)
    async with client:
        resp = await client.post("/api/v1/moves/fact", json={
            "fact_uid": str(fact.fact_uid),
            "target_node_uid": str(target_node.node_uid),
            "comment": "Contributor auto approve attempt",
            "auto_approve": True,
        })
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["status"] == "proposed"


# ════════════════════════════════════════════════════
# NODE MOVE TESTS
# ════════════════════════════════════════════════════


async def test_propose_node_move_creates_correlated_events(
    db: AsyncSession, contributor: FcUser, approver: FcUser,
    source_node: FcNode, target_node: FcNode,
    approver_source_perm: FcNodePermission,
    contrib_source_perm: FcNodePermission,
    contrib_target_perm: FcNodePermission,
) -> None:
    """Node with 3 facts creates 1 node event + 3 fact events, same correlation_id."""
    facts = []
    for _ in range(3):
        f, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)
        facts.append(f)

    client, _ = await _make_client(db, contributor)
    async with client:
        resp = await client.post("/api/v1/moves/node", json={
            "node_uid": str(source_node.node_uid),
            "target_parent_uid": str(target_node.node_uid),
            "comment": "Reorganize subtree",
        })
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "proposed"
    assert data["fact_count"] == 3
    assert data["correlation_id"] is not None

    # Verify events in DB
    corr = data["correlation_id"]
    stmt = select(FcEventLog).where(FcEventLog.event_type == "move.proposed")
    result = await db.execute(stmt)
    events = result.scalars().all()
    correlated = [e for e in events if (e.payload or {}).get("correlation_id") == corr]
    # 1 node + 3 facts
    assert len(correlated) == 4
    node_events = [e for e in correlated if e.entity_type == "node"]
    fact_events = [e for e in correlated if e.entity_type == "fact"]
    assert len(node_events) == 1
    assert len(fact_events) == 3


async def test_approve_node_move_moves_entire_subtree(
    db: AsyncSession, approver: FcUser,
    source_node: FcNode, target_node: FcNode, test_root: FcNode,
    approver_source_perm: FcNodePermission,
    approver_target_perm: FcNodePermission,
) -> None:
    """Approving a node move reparents the node and moves all facts."""
    facts = []
    for _ in range(3):
        f, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)
        facts.append(f)

    # Admin proposes (has global admin role, so contribute everywhere)
    client, _ = await _make_client(db, approver, auto_approve=False)
    async with client:
        resp = await client.post("/api/v1/moves/node", json={
            "node_uid": str(source_node.node_uid),
            "target_parent_uid": str(target_node.node_uid),
            "comment": "Reparent subtree",
        })
    app.dependency_overrides.clear()
    node_event_uid = resp.json()["event_uid"]

    # Approver approves
    client_a, _ = await _make_client(db, approver)
    async with client_a:
        resp = await client_a.post(f"/api/v1/moves/{node_event_uid}/approve")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["moved_count"] == 3

    await db.refresh(source_node)
    assert source_node.parent_node_uid == target_node.node_uid
    assert source_node.node_depth == 2  # target_node depth=1, so source is 2


async def test_reject_individual_fact_in_node_move(
    db: AsyncSession, contributor: FcUser, approver: FcUser,
    source_node: FcNode, target_node: FcNode,
    approver_source_perm: FcNodePermission,
    approver_target_perm: FcNodePermission,
    contrib_source_perm: FcNodePermission,
    contrib_target_perm: FcNodePermission,
) -> None:
    """Reject 1 of 3 facts, approve the rest via node approve."""
    facts = []
    for _ in range(3):
        f, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)
        facts.append(f)

    # Contributor proposes node move
    client_c, _ = await _make_client(db, contributor)
    async with client_c:
        resp = await client_c.post("/api/v1/moves/node", json={
            "node_uid": str(source_node.node_uid),
            "target_parent_uid": str(target_node.node_uid),
            "comment": "Partial rejection test",
        })
    app.dependency_overrides.clear()
    node_event_uid = resp.json()["event_uid"]
    correlation_id = resp.json()["correlation_id"]

    # Find fact-level events
    stmt = select(FcEventLog).where(
        FcEventLog.event_type == "move.proposed",
        FcEventLog.entity_type == "fact",
    )
    result = await db.execute(stmt)
    fact_events = [
        e for e in result.scalars().all()
        if (e.payload or {}).get("correlation_id") == correlation_id
    ]
    assert len(fact_events) == 3

    # Reject one fact
    reject_event = fact_events[0]
    client_a, _ = await _make_client(db, approver)
    async with client_a:
        resp = await client_a.post(
            f"/api/v1/moves/{reject_event.event_uid}/reject-fact",
            json={"note": "Keep this one"},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 200

    # Now approve the node move — should move 2, skip 1
    client_a2, _ = await _make_client(db, approver)
    async with client_a2:
        resp = await client_a2.post(f"/api/v1/moves/{node_event_uid}/approve")
    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["moved_count"] == 2
    assert resp.json()["rejected_count"] == 1


async def test_root_node_cannot_be_moved(
    db: AsyncSession, approver: FcUser, test_root: FcNode, target_node: FcNode,
    approver_source_perm: FcNodePermission,
    approver_target_perm: FcNodePermission,
) -> None:
    """Root nodes (depth 0) cannot be moved — returns 409."""
    client, _ = await _make_client(db, approver)
    async with client:
        resp = await client.post("/api/v1/moves/node", json={
            "node_uid": str(test_root.node_uid),
            "target_parent_uid": str(target_node.node_uid),
            "comment": "Try moving root",
        })
    app.dependency_overrides.clear()
    assert resp.status_code == 409


async def test_circular_move_rejected(
    db: AsyncSession, approver: FcUser,
    source_node: FcNode, child_of_source: FcNode,
    approver_source_perm: FcNodePermission,
) -> None:
    """Moving a node under its own descendant returns 409."""
    # Grant approver perm on child_of_source too
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=approver.user_uid,
        node_uid=child_of_source.node_uid,
        role="approver",
        granted_by_uid=approver.user_uid,
    )
    db.add(perm)
    await db.flush()

    client, _ = await _make_client(db, approver)
    async with client:
        resp = await client.post("/api/v1/moves/node", json={
            "node_uid": str(source_node.node_uid),
            "target_parent_uid": str(child_of_source.node_uid),
            "comment": "Circular move attempt",
        })
    app.dependency_overrides.clear()
    assert resp.status_code == 409


# ════════════════════════════════════════════════════
# HISTORY INTEGRATION TESTS
# ════════════════════════════════════════════════════


async def test_proposed_move_appears_in_fact_history(
    db: AsyncSession, contributor: FcUser, approver: FcUser,
    source_node: FcNode, target_node: FcNode,
    approver_source_perm: FcNodePermission,
    contrib_source_perm: FcNodePermission,
    contrib_target_perm: FcNodePermission,
) -> None:
    """A proposed move shows in fact history."""
    fact, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)

    client_c, _ = await _make_client(db, contributor)
    async with client_c:
        await client_c.post("/api/v1/moves/fact", json={
            "fact_uid": str(fact.fact_uid),
            "target_node_uid": str(target_node.node_uid),
            "comment": "History test move",
        })
    app.dependency_overrides.clear()

    client_a, _ = await _make_client(db, approver)
    async with client_a:
        resp = await client_a.get(f"/api/v1/facts/{fact.fact_uid}/history")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    move_events = resp.json()["data"]["move_events"]
    assert len(move_events) >= 1
    assert move_events[0]["event_type"] == "move.proposed"
    assert move_events[0]["target_node_uid"] == str(target_node.node_uid)


async def test_approved_move_appears_in_fact_history_with_breadcrumbs(
    db: AsyncSession, approver: FcUser,
    source_node: FcNode, target_node: FcNode,
    approver_source_perm: FcNodePermission,
    approver_target_perm: FcNodePermission,
) -> None:
    """An approved move (auto) shows in history with source/target UIDs."""
    fact, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)

    client, _ = await _make_client(db, approver, auto_approve=True)
    async with client:
        await client.post("/api/v1/moves/fact", json={
            "fact_uid": str(fact.fact_uid),
            "target_node_uid": str(target_node.node_uid),
            "comment": "Auto-moved",
            "auto_approve": True,
        })
    app.dependency_overrides.clear()

    client2, _ = await _make_client(db, approver)
    async with client2:
        resp = await client2.get(f"/api/v1/facts/{fact.fact_uid}/history")
    app.dependency_overrides.clear()

    move_events = resp.json()["data"]["move_events"]
    assert len(move_events) >= 1
    approved = [e for e in move_events if e["event_type"] == "move.approved"]
    assert len(approved) >= 1
    assert approved[0]["source_node_uid"] == str(source_node.node_uid)
    assert approved[0]["target_node_uid"] == str(target_node.node_uid)


async def test_rejected_move_appears_in_fact_history(
    db: AsyncSession, contributor: FcUser, approver: FcUser,
    source_node: FcNode, target_node: FcNode,
    approver_source_perm: FcNodePermission,
    approver_target_perm: FcNodePermission,
    contrib_source_perm: FcNodePermission,
    contrib_target_perm: FcNodePermission,
) -> None:
    """A rejected move shows in history."""
    fact, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)

    client_c, _ = await _make_client(db, contributor)
    async with client_c:
        resp = await client_c.post("/api/v1/moves/fact", json={
            "fact_uid": str(fact.fact_uid),
            "target_node_uid": str(target_node.node_uid),
            "comment": "Rejected move",
        })
    app.dependency_overrides.clear()
    event_uid = resp.json()["event_uid"]

    client_a, _ = await _make_client(db, approver)
    async with client_a:
        await client_a.post(
            f"/api/v1/moves/{event_uid}/reject",
            json={"note": "Not appropriate"},
        )
    app.dependency_overrides.clear()

    client3, _ = await _make_client(db, approver)
    async with client3:
        resp = await client3.get(f"/api/v1/facts/{fact.fact_uid}/history")
    app.dependency_overrides.clear()

    move_events = resp.json()["data"]["move_events"]
    rejected = [e for e in move_events if e["event_type"] == "move.rejected"]
    assert len(rejected) >= 1
    assert rejected[0]["note"] == "Not appropriate"


async def test_node_move_appears_in_each_facts_history(
    db: AsyncSession, approver: FcUser,
    source_node: FcNode, target_node: FcNode,
    approver_source_perm: FcNodePermission,
    approver_target_perm: FcNodePermission,
) -> None:
    """Node move events appear in each affected fact's history."""
    facts = []
    for _ in range(2):
        f, _ = await _create_fact_in_node(db, source_node, approver, auto_approve=True)
        facts.append(f)

    client, _ = await _make_client(db, approver, auto_approve=True)
    async with client:
        resp = await client.post("/api/v1/moves/node", json={
            "node_uid": str(source_node.node_uid),
            "target_parent_uid": str(target_node.node_uid),
            "comment": "Node move for history",
            "auto_approve": True,
        })
    app.dependency_overrides.clear()
    assert resp.json()["status"] == "moved"

    # Check each fact's history for move events
    for fact in facts:
        client2, _ = await _make_client(db, approver)
        async with client2:
            resp = await client2.get(f"/api/v1/facts/{fact.fact_uid}/history")
        app.dependency_overrides.clear()
        move_events = resp.json()["data"]["move_events"]
        approved = [e for e in move_events if e["event_type"] == "move.approved"]
        assert len(approved) >= 1
