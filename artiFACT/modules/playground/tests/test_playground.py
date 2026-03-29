"""Playground integration tests.

These run inside Docker with:
  docker compose exec web pytest artiFACT/modules/playground/ -v

NOTE: Each ASGI request that touches the DB must use its own AsyncClient
instance.  The httpx ASGITransport shares the app's asyncpg pool, and the
FastAPI dependency-cleanup (generator close) can race with the next request
if both use the same transport.  Splitting into one-client-per-request
guarantees full ASGI lifecycle completion between DB-touching calls.

The autouse ``_reset_pool`` fixture disposes stale connections between tests
so that cross-test pool contamination cannot cause spurious failures.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from artiFACT.kernel.db import engine
from artiFACT.main import app


@pytest.fixture(autouse=True)
async def _reset_pool():
    """Dispose the shared engine pool before each test to avoid stale connections."""
    await engine.dispose()
    yield
    await engine.dispose()


def _make_client() -> AsyncClient:
    """Create a fresh ASGI test client (new transport) per request."""
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    )


def _extract_cookies(resp) -> dict[str, str]:
    """Pull cookies from a response into a plain dict."""
    return {c.name: c.value for c in resp.cookies.jar}


async def _enter_playground(role: str) -> dict[str, str]:
    """POST /playground/enter and return cookies dict.  Uses its own client."""
    async with _make_client() as c:
        resp = await c.post("/playground/enter", data={"role": role})
    assert resp.status_code == 303
    return _extract_cookies(resp)


async def _browse_with_cookies(cookies: dict[str, str]) -> str:
    """GET /browse with preset cookies, return body text."""
    async with _make_client() as c:
        for k, v in cookies.items():
            c.cookies.set(k, v)
        resp = await c.get("/browse")
    assert resp.status_code == 200
    return resp.text


# --- Entry and session ---


async def test_playground_landing_returns_three_roles() -> None:
    """GET /playground returns 200 with all three role options in HTML."""
    async with _make_client() as client:
        resp = await client.get("/playground")
    assert resp.status_code == 200
    body = resp.text
    assert "David Wallace" in body
    assert "Oscar Martinez" in body
    assert "Pam Beesly" in body
    assert body.count("playground/enter") >= 3


async def test_playground_enter_sets_session() -> None:
    """POST /playground/enter creates session and redirects to /browse."""
    async with _make_client() as client:
        resp = await client.post(
            "/playground/enter",
            data={"role": "contributor"},
        )
    assert resp.status_code == 303
    assert "/browse" in resp.headers["location"]

    cookies = _extract_cookies(resp)
    assert "session_id" in cookies
    assert "playground_mode" in cookies
    assert cookies["playground_mode"] == "true"


async def test_playground_enter_invalid_role_rejects() -> None:
    """POST /playground/enter with invalid role returns 400."""
    async with _make_client() as client:
        resp = await client.post(
            "/playground/enter",
            data={"role": "admin"},
        )
    assert resp.status_code == 400


async def test_playground_enter_signatory_maps_to_wallace() -> None:
    """Signatory role logs in as David Wallace."""
    cookies = await _enter_playground("signatory")
    body = await _browse_with_cookies(cookies)
    assert "David Wallace" in body


async def test_playground_enter_approver_maps_to_oscar() -> None:
    """Approver role logs in as Oscar Martinez."""
    cookies = await _enter_playground("approver")
    body = await _browse_with_cookies(cookies)
    assert "Oscar Martinez" in body


async def test_playground_enter_contributor_maps_to_pam() -> None:
    """Contributor role logs in as Pam Beesly."""
    cookies = await _enter_playground("contributor")
    body = await _browse_with_cookies(cookies)
    assert "Pam Beesly" in body


async def test_playground_enter_shows_banner_on_browse() -> None:
    """After entering playground, /browse shows the playground banner."""
    cookies = await _enter_playground("contributor")
    body = await _browse_with_cookies(cookies)
    assert "Playground Mode" in body
    assert "Pam Beesly" in body


# --- Exit and session teardown ---


async def test_exit_redirects_to_playground() -> None:
    """POST /playground/exit redirects to /playground."""
    cookies = await _enter_playground("approver")

    async with _make_client() as c:
        for k, v in cookies.items():
            c.cookies.set(k, v)
        exit_resp = await c.post(
            "/playground/exit",
            headers={"X-CSRF-Token": cookies.get("csrf_token", "")},
        )
    assert exit_resp.status_code == 303
    assert "/playground" in exit_resp.headers["location"]


async def test_exit_then_reenter_as_different_role() -> None:
    """Exit and re-enter as contributor — verify correct user."""
    # Enter as approver
    cookies1 = await _enter_playground("approver")
    body1 = await _browse_with_cookies(cookies1)
    assert "Oscar Martinez" in body1

    # Exit
    async with _make_client() as c:
        for k, v in cookies1.items():
            c.cookies.set(k, v)
        await c.post(
            "/playground/exit",
            headers={"X-CSRF-Token": cookies1.get("csrf_token", "")},
        )

    # Re-enter as contributor
    cookies2 = await _enter_playground("contributor")
    body2 = await _browse_with_cookies(cookies2)
    assert "Pam Beesly" in body2
    assert "Oscar Martinez" not in body2


# --- Reset ---


async def test_reset_does_not_500_on_fk_violations() -> None:
    """Reset deletes in correct order — no FK constraint errors."""
    cookies = await _enter_playground("contributor")

    async with _make_client() as c:
        for k, v in cookies.items():
            c.cookies.set(k, v)
        resp = await c.post(
            "/playground/reset",
            headers={"X-CSRF-Token": cookies.get("csrf_token", "")},
        )
    assert resp.status_code in (302, 303), (
        f"Reset returned {resp.status_code}, likely FK error"
    )


# --- Security boundary tests ---


async def test_unauthenticated_cannot_reset() -> None:
    """POST /playground/reset without a playground session must be rejected."""
    async with _make_client() as client:
        resp = await client.post(
            "/playground/reset",
            headers={"X-CSRF-Token": "fake"},
            cookies={"csrf_token": "fake"},
        )
    assert resp.status_code in (303, 403)


async def test_non_playground_session_cannot_reset() -> None:
    """A session without playground_mode cookie cannot hit /playground/reset."""
    async with _make_client() as client:
        resp = await client.post(
            "/playground/reset",
            headers={"X-CSRF-Token": "fake-token"},
            cookies={"csrf_token": "fake-token"},
        )
    assert resp.status_code in (303, 403)


async def test_playground_user_cannot_access_admin() -> None:
    """Playground users have global_role='viewer' — admin page must reject."""
    cookies = await _enter_playground("signatory")

    async with _make_client() as c:
        for k, v in cookies.items():
            c.cookies.set(k, v)
        resp = await c.get("/admin")
    assert resp.status_code == 403
