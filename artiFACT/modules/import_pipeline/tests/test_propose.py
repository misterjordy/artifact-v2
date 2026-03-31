"""Import propose tests — fact creation, KEEP NEW edits, comments, guards, lifecycle."""

import json
import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, generate_csrf_token
from artiFACT.kernel.auth.session import create_session
from artiFACT.kernel.models import (
    FcFact,
    FcFactComment,
    FcFactVersion,
    FcImportSession,
    FcImportStagedFact,
    FcNode,
    FcNodePermission,
    FcUser,
)
from artiFACT.main import app


@pytest_asyncio.fixture
async def authed_client(db: AsyncSession, import_contributor: FcUser):
    """HTTP client with valid session cookie and CSRF token."""
    from artiFACT.kernel.db import get_db

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db

    session_id = await create_session(import_contributor)
    csrf_token = generate_csrf_token()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.cookies.set("session_id", session_id)
        client.cookies.set(CSRF_COOKIE_NAME, csrf_token)
        client.headers[CSRF_HEADER_NAME] = csrf_token
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def other_user_client(db: AsyncSession, root_node: FcNode):
    """HTTP client for a DIFFERENT user (not the session owner)."""
    from artiFACT.kernel.db import get_db

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db

    user = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=Other User {uuid.uuid4().hex[:8]}",
        display_name="Other User",
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

    session_id = await create_session(user)
    csrf_token = generate_csrf_token()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.cookies.set("session_id", session_id)
        client.cookies.set(CSRF_COOKIE_NAME, csrf_token)
        client.headers[CSRF_HEADER_NAME] = csrf_token
        yield client

    app.dependency_overrides.clear()


def _make_session(
    db: AsyncSession,
    contributor: FcUser,
    root_node: FcNode,
    status: str = "staged",
) -> FcImportSession:
    """Create a test import session."""
    session = FcImportSession(
        session_uid=uuid.uuid4(),
        program_node_uid=root_node.node_uid,
        source_filename="test-doc.txt",
        source_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        effective_date=date(2026, 1, 15),
        status=status,
        created_by_uid=contributor.user_uid,
    )
    db.add(session)
    return session


def _make_staged(
    db: AsyncSession,
    session: FcImportSession,
    sentence: str,
    node_uid: uuid.UUID,
    status: str = "pending",
    **kwargs,
) -> FcImportStagedFact:
    """Create a test staged fact."""
    sf = FcImportStagedFact(
        staged_fact_uid=uuid.uuid4(),
        session_uid=session.session_uid,
        display_sentence=sentence,
        suggested_node_uid=node_uid,
        status=status,
        source_chunk_index=kwargs.get("source_chunk_index", 0),
        node_alternatives=[],
        metadata_tags=[],
        **{k: v for k, v in kwargs.items() if k != "source_chunk_index"},
    )
    db.add(sf)
    return sf


# === Core propose ===


@pytest.mark.asyncio
async def test_propose_creates_facts_for_accepted_staged(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """Propose creates fc_fact + fc_fact_version for each accepted staged fact."""
    session = _make_session(db, import_contributor, root_node)
    for i in range(5):
        _make_staged(db, session, f"Accepted fact {i}.", root_node.node_uid, source_chunk_index=i)
    await db.flush()

    resp = await authed_client.post(
        f"/api/v1/import/sessions/{session.session_uid}/propose",
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["created"] == 5
    assert data["skipped"] == 0

    # Verify facts in DB
    facts = (await db.execute(
        select(FcFactVersion).where(FcFactVersion.state == "proposed")
    )).scalars().all()
    proposed_sentences = {v.display_sentence for v in facts}
    for i in range(5):
        assert f"Accepted fact {i}." in proposed_sentences

    # Verify session status
    await db.refresh(session)
    assert session.status == "proposed"


@pytest.mark.asyncio
async def test_propose_skips_rejected_orphaned_deleted(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """Propose skips rejected, orphaned, and deleted facts."""
    session = _make_session(db, import_contributor, root_node)
    for i in range(3):
        _make_staged(db, session, f"Good fact {i}.", root_node.node_uid, source_chunk_index=i)
    _make_staged(db, session, "Rejected fact.", root_node.node_uid, status="rejected", source_chunk_index=3)
    _make_staged(db, session, "Orphaned fact.", None, status="orphaned", source_chunk_index=4)
    _make_staged(db, session, "Deleted fact.", root_node.node_uid, status="deleted", source_chunk_index=5)
    await db.flush()

    resp = await authed_client.post(
        f"/api/v1/import/sessions/{session.session_uid}/propose",
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["created"] == 3
    assert data["skipped"] == 3


@pytest.mark.asyncio
async def test_propose_adds_import_comment_tag(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """Proposed facts get an #importYYYYMMDDHHMMSS comment."""
    session = _make_session(db, import_contributor, root_node)
    _make_staged(db, session, "Fact with comment.", root_node.node_uid)
    await db.flush()

    resp = await authed_client.post(
        f"/api/v1/import/sessions/{session.session_uid}/propose",
    )
    assert resp.status_code == 200

    # Find the comment
    comments = (await db.execute(select(FcFactComment))).scalars().all()
    assert len(comments) >= 1
    comment = comments[0]
    assert comment.body.startswith("#import2026")
    assert "test-doc.txt" in comment.body


@pytest.mark.asyncio
async def test_import_tag_same_for_all_facts_in_session(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """All facts in one propose call share the same #import tag."""
    session = _make_session(db, import_contributor, root_node)
    for i in range(5):
        _make_staged(db, session, f"Multi fact {i}.", root_node.node_uid, source_chunk_index=i)
    await db.flush()

    resp = await authed_client.post(
        f"/api/v1/import/sessions/{session.session_uid}/propose",
    )
    assert resp.status_code == 200

    comments = (await db.execute(select(FcFactComment))).scalars().all()
    assert len(comments) == 5
    tags = {c.body.split(" —")[0] for c in comments}
    assert len(tags) == 1  # All same tag


# === KEEP NEW ===


@pytest.mark.asyncio
async def test_keep_new_edits_existing_fact(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """KEEP NEW creates a proposed edit on the existing fact, not a new fact."""
    # Create existing fact + version
    existing_fact = FcFact(
        node_uid=root_node.node_uid,
        created_by_uid=import_contributor.user_uid,
    )
    db.add(existing_fact)
    await db.flush()

    existing_version = FcFactVersion(
        fact_uid=existing_fact.fact_uid,
        state="published",
        display_sentence="Old sensor range is 100km.",
        effective_date="2026-01-01",
        created_by_uid=import_contributor.user_uid,
    )
    db.add(existing_version)
    await db.flush()

    existing_fact.current_published_version_uid = existing_version.version_uid
    await db.flush()

    # Create session with keep_new staged fact
    session = _make_session(db, import_contributor, root_node)
    _make_staged(
        db, session, "New sensor range is 150km.", root_node.node_uid,
        status="accepted", resolution="keep_new",
        duplicate_of_uid=existing_version.version_uid,
    )
    await db.flush()

    resp = await authed_client.post(
        f"/api/v1/import/sessions/{session.session_uid}/propose",
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["edited"] == 1
    assert data["created"] == 0

    # Verify: new version on EXISTING fact, not a new fact
    versions = (await db.execute(
        select(FcFactVersion).where(FcFactVersion.fact_uid == existing_fact.fact_uid)
    )).scalars().all()
    assert len(versions) == 2  # original + edit
    new_v = [v for v in versions if v.version_uid != existing_version.version_uid][0]
    assert new_v.display_sentence == "New sensor range is 150km."
    assert new_v.state == "proposed"
    assert "Import correction" in (new_v.change_summary or "")


@pytest.mark.asyncio
async def test_keep_new_conflict_edits_existing(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """KEEP NEW for conflict creates proposed edit with conflict reason."""
    existing_fact = FcFact(
        node_uid=root_node.node_uid,
        created_by_uid=import_contributor.user_uid,
    )
    db.add(existing_fact)
    await db.flush()

    existing_version = FcFactVersion(
        fact_uid=existing_fact.fact_uid,
        state="published",
        display_sentence="System power is 50MW.",
        effective_date="2026-01-01",
        created_by_uid=import_contributor.user_uid,
    )
    db.add(existing_version)
    await db.flush()

    existing_fact.current_published_version_uid = existing_version.version_uid
    await db.flush()

    session = _make_session(db, import_contributor, root_node)
    _make_staged(
        db, session, "System power is 75MW.", root_node.node_uid,
        status="accepted", resolution="keep_new",
        conflict_with_uid=existing_version.version_uid,
        conflict_reason="Incompatible MW values",
    )
    await db.flush()

    resp = await authed_client.post(
        f"/api/v1/import/sessions/{session.session_uid}/propose",
    )
    assert resp.status_code == 200

    versions = (await db.execute(
        select(FcFactVersion).where(FcFactVersion.fact_uid == existing_fact.fact_uid)
    )).scalars().all()
    new_v = [v for v in versions if v.version_uid != existing_version.version_uid][0]
    assert "Incompatible MW values" in (new_v.change_summary or "")

    # Verify correction comment
    comments = (await db.execute(select(FcFactComment))).scalars().all()
    assert any("correction from" in c.body for c in comments)


# === Guards ===


@pytest.mark.asyncio
async def test_propose_requires_staged_status(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """Cannot propose a session that isn't 'staged'."""
    session = _make_session(db, import_contributor, root_node, status="proposed")
    await db.flush()

    resp = await authed_client.post(
        f"/api/v1/import/sessions/{session.session_uid}/propose",
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_propose_requires_session_owner(
    other_user_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """Only the session owner can propose."""
    session = _make_session(db, import_contributor, root_node)
    _make_staged(db, session, "Some fact.", root_node.node_uid)
    await db.flush()

    resp = await other_user_client.post(
        f"/api/v1/import/sessions/{session.session_uid}/propose",
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cannot_propose_empty_session(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """Cannot propose when all facts are deleted/rejected."""
    session = _make_session(db, import_contributor, root_node)
    _make_staged(db, session, "Deleted.", root_node.node_uid, status="deleted")
    _make_staged(db, session, "Rejected.", root_node.node_uid, status="rejected", source_chunk_index=1)
    await db.flush()

    resp = await authed_client.post(
        f"/api/v1/import/sessions/{session.session_uid}/propose",
    )
    assert resp.status_code == 409
    assert "No facts ready" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_propose_requires_all_facts_have_node(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """Cannot propose if any accepted fact has no target node."""
    session = _make_session(db, import_contributor, root_node)
    _make_staged(db, session, "Good fact.", root_node.node_uid)
    # This one is accepted but has no node
    sf = FcImportStagedFact(
        staged_fact_uid=uuid.uuid4(),
        session_uid=session.session_uid,
        display_sentence="No node fact.",
        suggested_node_uid=None,
        status="pending",
        source_chunk_index=1,
        node_alternatives=[],
        metadata_tags=[],
    )
    db.add(sf)
    await db.flush()

    resp = await authed_client.post(
        f"/api/v1/import/sessions/{session.session_uid}/propose",
    )
    assert resp.status_code == 409
    assert "no target node" in resp.json()["detail"]


# === Session lifecycle ===


@pytest.mark.asyncio
async def test_active_session_detected_on_page_load(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """Import page detects active staged session and passes it to template."""
    session = _make_session(db, import_contributor, root_node, status="staged")
    _make_staged(db, session, "Active fact.", root_node.node_uid)
    await db.flush()

    resp = await authed_client.get("/import")
    assert resp.status_code == 200
    # The active session data should be in the data-active-session attribute
    assert str(session.session_uid) in resp.text


@pytest.mark.asyncio
async def test_no_active_session_shows_entry_form(
    authed_client: AsyncClient,
):
    """Import page shows entry form when no active session exists."""
    resp = await authed_client.get("/import")
    assert resp.status_code == 200
    assert "Paste Text" in resp.text
    assert "Upload Document" in resp.text


# === Import history ===


@pytest.mark.asyncio
async def test_import_history_returns_user_sessions(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """GET /sessions?mine=true returns only the current user's sessions."""
    for i in range(3):
        s = FcImportSession(
            session_uid=uuid.uuid4(),
            program_node_uid=root_node.node_uid,
            source_filename=f"history-{i}.txt",
            source_hash=uuid.uuid4().hex + uuid.uuid4().hex,
            effective_date=date(2026, 1, 15),
            status="proposed",
            created_by_uid=import_contributor.user_uid,
        )
        db.add(s)
    await db.flush()

    resp = await authed_client.get("/api/v1/import/sessions?mine=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    filenames = {s["source_filename"] for s in data["data"]}
    assert "history-0.txt" in filenames


@pytest.mark.asyncio
async def test_import_history_includes_fact_counts(
    authed_client: AsyncClient,
    db: AsyncSession,
    import_contributor: FcUser,
    root_node: FcNode,
):
    """Session history includes total/proposed/skipped counts."""
    session = _make_session(db, import_contributor, root_node, status="proposed")
    _make_staged(db, session, "Proposed.", root_node.node_uid, status="accepted")
    _make_staged(db, session, "Skipped.", root_node.node_uid, status="rejected", source_chunk_index=1)
    await db.flush()

    resp = await authed_client.get("/api/v1/import/sessions?mine=true")
    assert resp.status_code == 200
    data = resp.json()["data"]
    s = [x for x in data if x["session_uid"] == str(session.session_uid)][0]
    assert s["total"] == 2
    assert s["proposed"] == 1
    assert s["skipped"] == 1
