"""Tests for arti chat widget rendering and PATCH filter endpoint."""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.db import engine
from artiFACT.kernel.models import FcChatSession, FcNode, FcUser
from artiFACT.main import app
from artiFACT.modules.ai_chat.session_manager import (
    create_session,
    get_session,
    update_fact_filter,
)
from artiFACT.modules.auth_admin.ai_key_manager import save_ai_key


# ── Helpers ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
async def _reset_pool():
    """Dispose the shared engine pool before each test."""
    await engine.dispose()
    yield
    await engine.dispose()


def _make_client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    )


async def _enter_playground(role: str) -> dict[str, str]:
    """POST /playground/enter and return cookies dict."""
    async with _make_client() as c:
        resp = await c.post("/playground/enter", data={"role": role})
    assert resp.status_code == 303
    return {c2.name: c2.value for c2 in resp.cookies.jar}


async def _get_page_html(path: str, cookies: dict[str, str]) -> str:
    """GET a page with cookies, return body text."""
    async with _make_client() as c:
        for k, v in cookies.items():
            c.cookies.set(k, v)
        resp = await c.get(path)
    if resp.status_code == 303:
        return ""
    return resp.text


# ── Widget rendering tests ───────────────────────────────────────────


class TestWidgetRendering:
    @pytest.mark.asyncio
    async def test_widget_renders_on_browse_page(self) -> None:
        cookies = await _enter_playground("approver")
        html = await _get_page_html("/browse", cookies)
        assert "artiChat" in html
        assert "arti_widget" in html or "arti.js" in html

    @pytest.mark.asyncio
    async def test_widget_renders_on_queue_page(self) -> None:
        cookies = await _enter_playground("approver")
        html = await _get_page_html("/queue", cookies)
        assert "artiChat" in html

    @pytest.mark.asyncio
    async def test_widget_renders_on_import_page(self) -> None:
        cookies = await _enter_playground("approver")
        html = await _get_page_html("/import", cookies)
        assert "artiChat" in html

    @pytest.mark.asyncio
    async def test_widget_not_rendered_when_unauthenticated(self) -> None:
        async with _make_client() as c:
            resp = await c.get("/browse")
        # Should redirect to login or not contain widget
        if resp.status_code == 303:
            assert True  # redirected, no widget
        else:
            assert "artiChat" not in resp.text


# ── PATCH filter endpoint ────────────────────────────────────────────


class TestPatchFilter:
    @pytest.mark.asyncio
    async def test_update_fact_filter(
        self, db: AsyncSession, contributor_user: FcUser, root_node: FcNode
    ) -> None:
        session = await create_session(
            db, contributor_user.user_uid, root_node.node_uid
        )
        assert session.fact_filter == "published"

        updated = await update_fact_filter(
            db, session.chat_uid, contributor_user.user_uid, "signed"
        )
        assert updated.fact_filter == "signed"

    @pytest.mark.asyncio
    async def test_update_filter_requires_owner(
        self, db: AsyncSession, contributor_user: FcUser,
        viewer_user: FcUser, root_node: FcNode
    ) -> None:
        session = await create_session(
            db, contributor_user.user_uid, root_node.node_uid
        )
        from artiFACT.kernel.exceptions import NotFound

        with pytest.raises(NotFound):
            await update_fact_filter(
                db, session.chat_uid, viewer_user.user_uid, "signed"
            )


# ── Active sessions API ─────────────────────────────────────────────


class TestActiveSessionsAPI:
    @pytest.mark.asyncio
    async def test_active_sessions_returns_data(
        self, db: AsyncSession, contributor_user: FcUser, root_node: FcNode
    ) -> None:
        from artiFACT.modules.ai_chat.session_manager import get_active_sessions

        s1 = await create_session(
            db, contributor_user.user_uid, root_node.node_uid
        )
        s2 = await create_session(
            db, contributor_user.user_uid, root_node.node_uid, mode="smart"
        )
        sessions = await get_active_sessions(db, contributor_user.user_uid)
        assert len(sessions) == 2
        uids = [s.chat_uid for s in sessions]
        assert s1.chat_uid in uids
        assert s2.chat_uid in uids
