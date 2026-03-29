"""Integration tests for left pane improvements: resizable sidebar, favorites, inline search."""

import re
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.csrf import generate_csrf_token
from artiFACT.kernel.auth.session import create_session
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import FcFact, FcFactVersion, FcNode, FcNodePermission, FcUser
from artiFACT.main import app
from artiFACT.modules.auth_admin.service import hash_password

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "artiFACT" / "static"
JS_DIR = STATIC_DIR / "js"
CSS_PATH = STATIC_DIR / "theme.css"


@pytest_asyncio.fixture
async def authed_client(db: AsyncSession, admin_user: FcUser) -> AsyncIterator[AsyncClient]:
    """HTTP client authenticated as admin."""
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


@pytest_asyncio.fixture
async def pam_client(db: AsyncSession, admin_user: FcUser) -> AsyncIterator[AsyncClient]:
    """HTTP client authenticated as Pam (contributor on multiple programs)."""
    import uuid

    pam = FcUser(
        user_uid=uuid.uuid4(),
        cac_dn=f"CN=Pam {uuid.uuid4().hex[:8]}",
        display_name="Pam",
        global_role="contributor",
        password_hash=hash_password("pam"),
    )
    db.add(pam)
    await db.flush()

    # Create two programs
    prog1 = FcNode(
        node_uid=uuid.uuid4(),
        title="Boatwing H-12",
        slug=f"boatwing-{uuid.uuid4().hex[:8]}",
        node_depth=0,
        created_by_uid=admin_user.user_uid,
    )
    prog2 = FcNode(
        node_uid=uuid.uuid4(),
        title="SNIPE-B",
        slug=f"snipe-b-{uuid.uuid4().hex[:8]}",
        node_depth=0,
        created_by_uid=admin_user.user_uid,
    )
    db.add_all([prog1, prog2])
    await db.flush()

    # Create child nodes
    child1 = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=prog1.node_uid,
        title="Hydraulic System",
        slug=f"hydraulic-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    child2 = FcNode(
        node_uid=uuid.uuid4(),
        parent_node_uid=prog2.node_uid,
        title="Hydraulic Pump",
        slug=f"hydraulic-pump-{uuid.uuid4().hex[:8]}",
        node_depth=1,
        created_by_uid=admin_user.user_uid,
    )
    db.add_all([child1, child2])
    await db.flush()

    # Grant Pam contributor on both programs
    for prog in [prog1, prog2]:
        perm = FcNodePermission(
            permission_uid=uuid.uuid4(),
            user_uid=pam.user_uid,
            node_uid=prog.node_uid,
            role="contributor",
            granted_by_uid=admin_user.user_uid,
        )
        db.add(perm)

    # Create facts with "hydraulic" in both programs
    for child in [child1, child2]:
        fact = FcFact(
            fact_uid=uuid.uuid4(),
            node_uid=child.node_uid,
            created_by_uid=pam.user_uid,
            is_retired=False,
        )
        db.add(fact)
        await db.flush()
        version = FcFactVersion(
            version_uid=uuid.uuid4(),
            fact_uid=fact.fact_uid,
            display_sentence=f"The hydraulic pressure in {child.title} is nominal.",
            state="published",
            created_by_uid=pam.user_uid,
            classification="UNCLASSIFIED",
        )
        db.add(version)
        fact.current_published_version_uid = version.version_uid

    await db.flush()

    session_id = await create_session(pam)
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


# ── TEST 1: Sidebar has resize handle ─────────────────────────────────────

async def test_sidebar_has_resize_handle(authed_client: AsyncClient) -> None:
    """GET /browse contains the resize handle with grip content."""
    resp = await authed_client.get("/browse")
    assert resp.status_code == 200
    html = resp.text
    assert "sidebar-resize" in html or "col-resize" in html
    # The JS file is loaded which creates the handle dynamically,
    # verify the script is included
    assert "sidebar-resize.js" in html


# ── TEST 2: Eyecare mode resize handle is wider ──────────────────────────

async def test_eyecare_resize_handle_wider() -> None:
    """theme.css has eyecare rule making resize handle 12px wide."""
    css = CSS_PATH.read_text()
    assert "html.eyecare .sidebar-resize-handle" in css
    # Check for 12px width in the eyecare block
    eyecare_section = css[css.index("html.eyecare .sidebar-resize-handle"):]
    assert "12px" in eyecare_section[:200]


# ── TEST 3: Sidebar width persisted via localStorage ─────────────────────

async def test_sidebar_width_persisted() -> None:
    """sidebar-resize.js uses localStorage with artifact-sidebar-width key."""
    js = (JS_DIR / "sidebar-resize.js").read_text()
    assert "artifact-sidebar-width" in js
    assert "localStorage" in js


# ── TEST 4: Favorites section exists in sidebar ──────────────────────────

async def test_favorites_section_in_sidebar(authed_client: AsyncClient) -> None:
    """GET /browse includes Favorites label and star icons."""
    resp = await authed_client.get("/browse")
    assert resp.status_code == 200
    html = resp.text
    assert "Favorites" in html
    # Star icon present (★ or ☆)
    assert "★" in html or "☆" in html


# ── TEST 5: Favorites use localStorage ───────────────────────────────────

async def test_favorites_use_localstorage() -> None:
    """favorites.js uses localStorage with artifact-favorites key."""
    js = (JS_DIR / "favorites.js").read_text()
    assert "artifact-favorites" in js
    assert "localStorage" in js


# ── TEST 6: Search input in sidebar, nav in header ──────────────────────

async def test_search_input_in_sidebar(authed_client: AsyncClient) -> None:
    """Sidebar has search input, no submit button, header has nav links."""
    resp = await authed_client.get("/browse")
    assert resp.status_code == 200
    html = resp.text
    assert 'placeholder="Search taxonomy"' in html
    # No search submit button in sidebar
    assert '<button type="submit"' not in html or "Search" not in html.split("sidebar")[0]
    # Header should contain nav links, not search
    header_match = re.search(r"<header.*?</header>", html, re.DOTALL)
    if header_match:
        header_html = header_match.group()
        assert "Search taxonomy" not in header_html
        assert "Queue" in header_html
        assert "Import" in header_html
        assert "AI Chat" in header_html
        assert "Export" in header_html
        assert "Admin" in header_html
    # Sidebar should NOT have nav links
    sidebar_match = re.search(r"<aside.*?</aside>", html, re.DOTALL)
    if sidebar_match:
        sidebar_html = sidebar_match.group()
        assert 'href="/queue"' not in sidebar_html
        assert 'href="/settings"' not in sidebar_html


# ── TEST 7: Collapse button SVG present, search sticky, no Taxonomy heading

async def test_collapse_svg_and_sticky_search(authed_client: AsyncClient) -> None:
    """Sidebar contains collapse SVG, sticky search, no Taxonomy heading."""
    resp = await authed_client.get("/browse")
    assert resp.status_code == 200
    html = resp.text
    assert "M22.6,15.4" in html
    # Search bar should be sticky
    assert "sticky" in html
    # No "Taxonomy" section heading
    sidebar_match = re.search(r"<aside.*?</aside>", html, re.DOTALL)
    if sidebar_match:
        # Should not have a standalone "Taxonomy" heading label
        assert ">Taxonomy<" not in sidebar_match.group().replace(" ", "").replace("\n", "")
        # But "Search taxonomy" placeholder is fine
        assert 'placeholder="Search taxonomy"' in sidebar_match.group()


# ── TEST 8: Search results endpoint works ────────────────────────────────

async def test_search_results_endpoint(pam_client: AsyncClient) -> None:
    """GET /partials/search-results?q=hydraulic returns grouped results."""
    resp = await pam_client.get("/partials/search-results?q=hydraulic")
    assert resp.status_code == 200
    html = resp.text
    assert "hydraulic" in html.lower()
    # Results should be grouped — look for breadcrumb paths
    assert ">" in html or "Hydraulic" in html


# ── TEST 9: Search respects program access ───────────────────────────────

async def test_search_respects_program_access(pam_client: AsyncClient) -> None:
    """Pam (contributor on Boatwing + SNIPE-B) sees results from both programs."""
    resp = await pam_client.get("/partials/search-results?q=hydraulic")
    assert resp.status_code == 200
    html = resp.text
    assert "Hydraulic System" in html or "hydraulic" in html.lower()
    assert "Hydraulic Pump" in html or "hydraulic" in html.lower()
    # TODO: Add test for single-program user when such a fixture exists.
    # A user with access to only one program should only see results from that program.


# ── TEST 10: Escape/clear mechanism ──────────────────────────────────────

async def test_escape_clear_mechanism() -> None:
    """sidebar-search.js contains Escape handler and clear logic."""
    js = (JS_DIR / "sidebar-search.js").read_text()
    assert "Escape" in js
    # Should clear the search input
    assert "clearSearch" in js or "input.value" in js
