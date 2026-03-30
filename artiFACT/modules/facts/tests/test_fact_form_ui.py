"""Integration tests for the fact form UI partial endpoints."""

import re
import uuid
from collections.abc import AsyncIterator
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.csrf import generate_csrf_token
from artiFACT.kernel.auth.session import create_session, update_session_field
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
from artiFACT.modules.auth_admin.service import hash_password
from artiFACT.scripts.seed_v1_data import (
    DWALLACE_UID,
    OMARTINEZ_UID,
    PBEESLY_UID,
)


# ── Fixtures ──


@pytest_asyncio.fixture
async def pam(db: AsyncSession) -> FcUser:
    """Pam Beesly — contributor."""
    user = FcUser(
        user_uid=PBEESLY_UID,
        cac_dn="pbeesly",
        display_name="Pam Beesly",
        global_role="viewer",
        is_active=True,
        password_hash=hash_password("playground2026"),
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def oscar(db: AsyncSession) -> FcUser:
    """Oscar Martinez — approver."""
    user = FcUser(
        user_uid=OMARTINEZ_UID,
        cac_dn="omartinez",
        display_name="Oscar Martinez",
        global_role="viewer",
        is_active=True,
        password_hash=hash_password("playground2026"),
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def david(db: AsyncSession) -> FcUser:
    """David Wallace — signatory on root only."""
    user = FcUser(
        user_uid=DWALLACE_UID,
        cac_dn="dwallace",
        display_name="David Wallace",
        global_role="viewer",
        is_active=True,
        password_hash=hash_password("playground2026"),
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def test_root(db: AsyncSession, admin_user: FcUser) -> FcNode:
    """Root node for fact form tests."""
    node = FcNode(
        node_uid=uuid.uuid4(),
        title="Fact Form Test Root",
        slug=f"ff-root-{uuid.uuid4().hex[:8]}",
        node_depth=0,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


@pytest_asyncio.fixture
async def test_node(db: AsyncSession, test_root: FcNode, admin_user: FcUser) -> FcNode:
    """Child node where Pam/Oscar have permissions."""
    node = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=test_root.node_uid,
        title="Fact Form Test Node",
        slug=f"ff-node-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


@pytest_asyncio.fixture
async def isolated_node(db: AsyncSession, admin_user: FcUser) -> FcNode:
    """A separate root node where David has NO permissions."""
    node = FcNode(
        node_uid=uuid.uuid4(),
        title="Isolated Node",
        slug=f"isolated-{uuid.uuid4().hex[:8]}",
        node_depth=0,
        created_by_uid=admin_user.user_uid,
    )
    db.add(node)
    await db.flush()
    return node


@pytest_asyncio.fixture
async def pam_permission(
    db: AsyncSession, pam: FcUser, test_node: FcNode, admin_user: FcUser
) -> FcNodePermission:
    """Grant Pam contributor on test_node."""
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=pam.user_uid,
        node_uid=test_node.node_uid,
        role="contributor",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()
    return perm


@pytest_asyncio.fixture
async def oscar_permission(
    db: AsyncSession, oscar: FcUser, test_node: FcNode, admin_user: FcUser
) -> FcNodePermission:
    """Grant Oscar approver on test_node."""
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=oscar.user_uid,
        node_uid=test_node.node_uid,
        role="approver",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()
    return perm


@pytest_asyncio.fixture
async def david_root_perm(
    db: AsyncSession, david: FcUser, test_root: FcNode, admin_user: FcUser
) -> FcNodePermission:
    """Grant David signatory on the root node (not on isolated_node)."""
    perm = FcNodePermission(
        permission_uid=uuid.uuid4(),
        user_uid=david.user_uid,
        node_uid=test_root.node_uid,
        role="signatory",
        granted_by_uid=admin_user.user_uid,
    )
    db.add(perm)
    await db.flush()
    return perm


async def _make_client(
    db: AsyncSession, user: FcUser, *, with_csrf: bool = True,
    auto_approve: bool = False,
) -> AsyncClient:
    """Build an authenticated AsyncClient for the given user."""
    session_id = await create_session(user)
    if auto_approve:
        await update_session_field(session_id, "auto_approve", True)
    csrf_token = generate_csrf_token()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    cookies = {"session_id": session_id, "csrf_token": csrf_token}
    headers = {"x-csrf-token": csrf_token} if with_csrf else {}
    transport = ASGITransport(app=app)
    return AsyncClient(
        transport=transport, base_url="http://test", cookies=cookies, headers=headers,
    )


async def _make_unauthed_client(db: AsyncSession) -> AsyncClient:
    """Build an unauthenticated AsyncClient."""
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ── TEST 1: CSRF not blocking form submission ──


async def test_csrf_not_blocking_form_post(
    db: AsyncSession, pam: FcUser, test_node: FcNode, pam_permission: FcNodePermission
) -> None:
    """POST /partials/fact-form succeeds with valid session (CSRF exempt)."""
    client = await _make_client(db, pam)
    async with client:
        sentence = f"CSRF test fact {uuid.uuid4().hex}"
        resp = await client.post(
            "/partials/fact-form",
            data={
                "node_uid": str(test_node.node_uid),
                "sentence": sentence,
                "classification": "UNCLASSIFIED",
            },
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    app.dependency_overrides.clear()


async def test_csrf_exempt_still_requires_auth(
    db: AsyncSession, test_node: FcNode, pam: FcUser, pam_permission: FcNodePermission
) -> None:
    """POST /partials/fact-form without auth returns 401 (CSRF exempt != open)."""
    client = await _make_unauthed_client(db)
    async with client:
        resp = await client.post(
            "/partials/fact-form",
            data={
                "node_uid": str(test_node.node_uid),
                "sentence": f"No auth test {uuid.uuid4().hex}",
            },
        )
        assert resp.status_code == 401
    app.dependency_overrides.clear()


async def test_csrf_enforced_on_non_exempt_endpoint(
    db: AsyncSession, pam: FcUser, test_node: FcNode, pam_permission: FcNodePermission
) -> None:
    """POST to a non-exempt endpoint without X-CSRF-Token header returns 403.

    Proves the CSRF middleware is still active — adding partials to the exempt
    list didn't break enforcement on other endpoints.
    """
    client = await _make_client(db, pam, with_csrf=False)
    async with client:
        resp = await client.post(
            "/api/v1/facts",
            json={
                "node_uid": str(test_node.node_uid),
                "sentence": f"CSRF enforcement check {uuid.uuid4().hex}",
            },
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
        assert "CSRF" in resp.text
    app.dependency_overrides.clear()


# ── TEST 2: Fact actually created in database ──


async def test_fact_created_in_database(
    db: AsyncSession, pam: FcUser, test_node: FcNode, pam_permission: FcNodePermission
) -> None:
    """POST creates a fact version with state=proposed for contributor Pam."""
    sentence = f"Database creation test {uuid.uuid4().hex}"
    client = await _make_client(db, pam)
    async with client:
        resp = await client.post(
            "/partials/fact-form",
            data={
                "node_uid": str(test_node.node_uid),
                "sentence": sentence,
                "classification": "UNCLASSIFIED",
            },
        )
        assert resp.status_code == 200

    app.dependency_overrides.clear()

    result = await db.execute(
        select(FcFactVersion).where(FcFactVersion.display_sentence == sentence)
    )
    version = result.scalar_one_or_none()
    assert version is not None, "Version not found in database"
    assert version.state == "proposed"
    assert version.created_by_uid == pam.user_uid

    fact = await db.get(FcFact, version.fact_uid)
    assert fact is not None
    assert fact.node_uid == test_node.node_uid


# ── TEST 3: Approver creates as published ──


async def test_approver_creates_published(
    db: AsyncSession,
    oscar: FcUser,
    test_node: FcNode,
    oscar_permission: FcNodePermission,
) -> None:
    """Approver Oscar auto-publishes facts on creation when auto_approve is ON."""
    sentence = f"Approver publish test {uuid.uuid4().hex}"
    client = await _make_client(db, oscar, auto_approve=True)
    async with client:
        resp = await client.post(
            "/partials/fact-form",
            data={
                "node_uid": str(test_node.node_uid),
                "sentence": sentence,
                "classification": "UNCLASSIFIED",
            },
        )
        assert resp.status_code == 200

    app.dependency_overrides.clear()

    result = await db.execute(
        select(FcFactVersion).where(FcFactVersion.display_sentence == sentence)
    )
    version = result.scalar_one_or_none()
    assert version is not None, "Version not found in database"
    assert version.state == "published"
    assert version.published_at is not None

    fact = await db.get(FcFact, version.fact_uid)
    assert fact is not None
    assert fact.current_published_version_uid == version.version_uid


# ── TEST 4: Classification dropdown values ──


async def test_classification_dropdown_values(
    db: AsyncSession, pam: FcUser, test_node: FcNode, pam_permission: FcNodePermission
) -> None:
    """Form contains only UNCLASSIFIED, CUI, CONFIDENTIAL — no SECRET options."""
    client = await _make_client(db, pam)
    async with client:
        resp = await client.get(f"/partials/fact-form?node={test_node.node_uid}")
        assert resp.status_code == 200

    app.dependency_overrides.clear()

    body = resp.text
    assert "UNCLASSIFIED" in body
    assert "CUI" in body
    assert "CONFIDENTIAL" in body

    secret_options = re.findall(r'<option[^>]*value="SECRET"', body)
    assert len(secret_options) == 0, f"Found SECRET option(s): {secret_options}"

    top_secret_options = re.findall(r'<option[^>]*value="TOP SECRET"', body)
    assert len(top_secret_options) == 0, f"Found TOP SECRET option(s): {top_secret_options}"


# ── TEST 5: Effective date defaults to today ──


async def test_effective_date_defaults_to_today(
    db: AsyncSession, pam: FcUser, test_node: FcNode, pam_permission: FcNodePermission
) -> None:
    """Form date input defaults to today; omitted effective_date saves as today."""
    today = date.today().isoformat()

    client = await _make_client(db, pam)
    async with client:
        resp = await client.get(f"/partials/fact-form?node={test_node.node_uid}")
        assert resp.status_code == 200
        assert today in resp.text, f"Today's date {today} not in form HTML"

        sentence = f"Date default test {uuid.uuid4().hex}"
        resp = await client.post(
            "/partials/fact-form",
            data={
                "node_uid": str(test_node.node_uid),
                "sentence": sentence,
                "classification": "UNCLASSIFIED",
            },
        )
        assert resp.status_code == 200

    app.dependency_overrides.clear()

    result = await db.execute(
        select(FcFactVersion).where(FcFactVersion.display_sentence == sentence)
    )
    version = result.scalar_one_or_none()
    assert version is not None
    assert str(version.effective_date) == today


# ── TEST 6: Cancel button markup exists ──


async def test_cancel_button_markup(
    db: AsyncSession, pam: FcUser, test_node: FcNode, pam_permission: FcNodePermission
) -> None:
    """Cancel button exists with an Alpine.js click handler dispatching closeModal."""
    client = await _make_client(db, pam)
    async with client:
        resp = await client.get(f"/partials/fact-form?node={test_node.node_uid}")
        assert resp.status_code == 200

    app.dependency_overrides.clear()

    body = resp.text
    assert "Cancel" in body

    has_alpine_handler = (
        "@click" in body or "x-on:click" in body
    )
    assert has_alpine_handler, "Cancel button has no Alpine.js click handler"
    assert "closeModal" in body, "No closeModal dispatch found in form HTML"


# ── TEST 7: Permission gating ──


async def test_permission_gating_forbidden(
    db: AsyncSession,
    david: FcUser,
    isolated_node: FcNode,
    david_root_perm: FcNodePermission,
) -> None:
    """David (signatory on root) gets 403 on an isolated node he has no perms on."""
    client = await _make_client(db, david)
    async with client:
        resp = await client.get(f"/partials/fact-form?node={isolated_node.node_uid}")
        assert resp.status_code == 403
    app.dependency_overrides.clear()


async def test_permission_gating_unauthenticated(
    db: AsyncSession, test_node: FcNode, pam: FcUser, pam_permission: FcNodePermission
) -> None:
    """Unauthenticated user gets 401 on GET /partials/fact-form."""
    client = await _make_unauthed_client(db)
    async with client:
        resp = await client.get(f"/partials/fact-form?node={test_node.node_uid}")
        assert resp.status_code == 401
    app.dependency_overrides.clear()


# ── TEST 8: Event log written ──


async def test_event_log_written(
    db: AsyncSession, pam: FcUser, test_node: FcNode, pam_permission: FcNodePermission
) -> None:
    """Creating a fact writes a fact.created event to fc_event_log.

    Note: the service emits 'fact.created' for all new facts regardless of role
    (see facts/service.py:68). The recorder stores this as event_type='fact.created'
    with entity_type='fact'. There is no separate 'fact.proposed' event — the
    version state (proposed vs published) is captured in the event payload.
    """
    sentence = f"Event log test {uuid.uuid4().hex}"
    client = await _make_client(db, pam)
    async with client:
        resp = await client.post(
            "/partials/fact-form",
            data={
                "node_uid": str(test_node.node_uid),
                "sentence": sentence,
                "classification": "UNCLASSIFIED",
            },
        )
        assert resp.status_code == 200

    app.dependency_overrides.clear()

    version_result = await db.execute(
        select(FcFactVersion).where(FcFactVersion.display_sentence == sentence)
    )
    version = version_result.scalar_one()

    event_result = await db.execute(
        select(FcEventLog).where(
            FcEventLog.entity_type == "fact",
            FcEventLog.entity_uid == version.fact_uid,
            FcEventLog.event_type == "fact.created",
        )
    )
    events = event_result.scalars().all()
    assert len(events) >= 1, "No fact.created event found in fc_event_log"
