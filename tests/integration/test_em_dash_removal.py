"""Verify page titles use pipe separators, not em dashes."""

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
from artiFACT.kernel.models import FcUser
from artiFACT.main import app

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "artiFACT" / "templates"


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
async def unauthed_client(db: AsyncSession) -> AsyncIterator[AsyncClient]:
    """HTTP client with no auth (for login page)."""

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as c:
        yield c
    app.dependency_overrides.clear()


def extract_title(html: str) -> str | None:
    """Extract content of <title> tag from HTML."""
    m = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
    return m.group(1).strip() if m else None


# ── TEST 1: No em dashes in page titles ──

AUTHED_PAGES = ["/browse", "/queue", "/import", "/chat", "/export", "/admin", "/settings"]


@pytest.mark.parametrize("path", AUTHED_PAGES)
async def test_authed_page_title_no_em_dash(authed_client: AsyncClient, path: str) -> None:
    """Authenticated pages must not use em dash in <title>."""
    resp = await authed_client.get(path)
    assert resp.status_code == 200, f"{path} returned {resp.status_code}"
    title = extract_title(resp.text)
    assert title is not None, f"{path} has no <title> tag"
    assert " — " not in title, f"{path} title contains em dash: {title}"
    assert "&mdash;" not in title, f"{path} title contains &mdash;: {title}"
    assert " | " in title or title == "artiFACT", f"{path} title missing pipe separator: {title}"


async def test_login_page_title_no_em_dash(unauthed_client: AsyncClient) -> None:
    """Login page must not use em dash in <title>."""
    resp = await unauthed_client.get("/")
    assert resp.status_code == 200
    title = extract_title(resp.text)
    assert title is not None, "Login page has no <title> tag"
    assert " — " not in title, f"Login title contains em dash: {title}"
    assert "&mdash;" not in title, f"Login title contains &mdash;: {title}"
    assert " | " in title or title == "artiFACT", f"Login title missing pipe separator: {title}"


async def test_playground_page_title_no_em_dash(unauthed_client: AsyncClient) -> None:
    """Playground page must not use em dash in <title>."""
    resp = await unauthed_client.get("/playground")
    # May redirect or return 200 depending on config
    if resp.status_code == 200:
        title = extract_title(resp.text)
        assert title is not None
        assert " — " not in title, f"Playground title contains em dash: {title}"
        assert "&mdash;" not in title
        assert " | " in title or title == "artiFACT"


# ── TEST 2: No em dashes in template source title blocks ──

TITLE_EM_DASH_RE = re.compile(r"(block title|<title>).*?—.*?(endblock|</title>)")


async def test_template_sources_no_em_dash_in_titles() -> None:
    """No template source file should have em dash in title/block title context."""
    violations: list[str] = []
    for html_file in sorted(TEMPLATE_DIR.rglob("*.html")):
        text = html_file.read_text()
        rel = html_file.relative_to(TEMPLATE_DIR)
        for i, line in enumerate(text.splitlines(), 1):
            if TITLE_EM_DASH_RE.search(line):
                violations.append(f"{rel}:{i}: {line.strip()}")
    assert violations == [], f"Em dashes found in title context:\n" + "\n".join(violations)


# ── TEST 3: Pipe separator is consistent across all pages ──


async def test_consistent_pipe_separator(
    authed_client: AsyncClient, unauthed_client: AsyncClient
) -> None:
    """All page titles with a separator must use ' | ' consistently."""
    titles: dict[str, str] = {}

    # Authed pages
    for path in AUTHED_PAGES:
        resp = await authed_client.get(path)
        if resp.status_code == 200:
            title = extract_title(resp.text)
            if title:
                titles[path] = title

    # Login page
    resp = await unauthed_client.get("/")
    if resp.status_code == 200:
        title = extract_title(resp.text)
        if title:
            titles["/login"] = title

    # Check all titles with separators use pipe
    bad_separators: list[str] = []
    for path, title in titles.items():
        if title == "artiFACT":
            continue
        if " | " not in title:
            bad_separators.append(f"{path}: {title}")
        # Check for mixed separators
        for sep in [" — ", " - ", " · ", " – "]:
            if sep in title:
                bad_separators.append(f"{path} uses '{sep}': {title}")

    assert bad_separators == [], "Inconsistent title separators:\n" + "\n".join(bad_separators)
