"""Tests for chat service: integration with real permissions, events, encryption. Only LLM httpx calls mocked."""

import json
import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import (
    FcFact,
    FcFactVersion,
    FcNode,
    FcNodePermission,
    FcUser,
)
from artiFACT.modules.ai_chat.service import NoAIKeyError, chat, chat_stream
from artiFACT.modules.auth_admin.ai_key_manager import save_ai_key


@pytest_asyncio.fixture
async def user_with_key(db: AsyncSession, contributor_user: FcUser) -> FcUser:
    """Contributor user with an OpenAI key saved."""
    await save_ai_key(db, contributor_user.user_uid, "openai", "sk-test-abcdef1234")
    return contributor_user


@pytest_asyncio.fixture
async def node_with_facts(
    db: AsyncSession, admin_user: FcUser, child_node: FcNode
) -> tuple[FcNode, list[str]]:
    """child_node with 3 published facts."""
    sentences = [
        "The system uses AES-256-GCM encryption for all data at rest.",
        "Authentication is handled via CAC/PKI certificate validation.",
        "Rate limiting is enforced at 50 requests per hour per user.",
    ]
    for sentence in sentences:
        fact = FcFact(
            fact_uid=uuid.uuid4(),
            node_uid=child_node.node_uid,
            created_by_uid=admin_user.user_uid,
        )
        db.add(fact)
        await db.flush()
        ver = FcFactVersion(
            version_uid=uuid.uuid4(),
            fact_uid=fact.fact_uid,
            state="published",
            display_sentence=sentence,
            created_by_uid=admin_user.user_uid,
        )
        db.add(ver)
        await db.flush()
        fact.current_published_version_uid = ver.version_uid
        await db.flush()
    return child_node, sentences


def _mock_openai_response(content: str = "The system uses AES-256 encryption.") -> httpx.Response:
    """Build a fake OpenAI chat completions response."""
    return httpx.Response(
        status_code=200,
        json={
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        },
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )


class TestChat:
    @pytest.mark.asyncio
    async def test_no_key_returns_clear_error_message(
        self,
        db: AsyncSession,
        contributor_user: FcUser,
    ) -> None:
        """DoS: no key → clear error message."""
        with pytest.raises(NoAIKeyError) as exc_info:
            await chat(db, contributor_user, "Hello", None, [])
        assert "No AI API key configured" in str(exc_info.value.detail)
        assert "Settings" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_chat_returns_response(
        self,
        db: AsyncSession,
        user_with_key: FcUser,
        contributor_permission: FcNodePermission,
        node_with_facts: tuple[FcNode, list[str]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Full chat flow with mocked httpx only."""
        node, _ = node_with_facts
        mock_response = _mock_openai_response("The system uses AES-256 encryption.")
        mock_post = AsyncMock(return_value=mock_response)
        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        result = await chat(
            db=db,
            user=user_with_key,
            message="What encryption does the system use?",
            node_uid=node.node_uid,
            history=[],
        )
        assert "content" in result
        assert result["facts_loaded"] > 0
        assert result["facts_total"] > 0

    @pytest.mark.asyncio
    async def test_streaming_response_works(
        self,
        db: AsyncSession,
        user_with_key: FcUser,
        contributor_permission: FcNodePermission,
        node_with_facts: tuple[FcNode, list[str]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """DoS: streaming response works end to end."""
        node, _ = node_with_facts

        # Mock httpx stream for OpenAI
        chunks = [
            b'data: {"choices":[{"delta":{"content":"Hello "}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"world."}}]}\n\n',
            b'data: [DONE]\n\n',
        ]

        class FakeStreamResponse:
            status_code = 200

            def raise_for_status(self) -> None:
                pass

            async def aiter_lines(self):
                for chunk in chunks:
                    for line in chunk.decode().strip().split("\n"):
                        if line:
                            yield line

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        class FakeClient:
            def __init__(self, **kwargs):
                pass

            def stream(self, method, url, **kwargs):
                return FakeStreamResponse()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        monkeypatch.setattr("artiFACT.modules.ai_chat.service.httpx.AsyncClient", FakeClient)

        collected: list[str] = []
        async for chunk in chat_stream(
            db=db,
            user=user_with_key,
            message="Hello",
            node_uid=node.node_uid,
            history=[],
        ):
            collected.append(chunk)

        all_text = "".join(collected)
        assert "meta" in all_text
        assert "chunk" in all_text or "DONE" in all_text


class TestRateLimit:
    @pytest.mark.asyncio
    async def test_rate_limited_per_user(
        self,
        db: AsyncSession,
        user_with_key: FcUser,
        contributor_permission: FcNodePermission,
        node_with_facts: tuple[FcNode, list[str]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """DoS: rate limited per user."""
        from artiFACT.kernel.exceptions import RateLimited

        node, _ = node_with_facts
        mock_response = _mock_openai_response()
        mock_post = AsyncMock(return_value=mock_response)
        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        # Override rate limit to a small number for testing
        import artiFACT.kernel.rate_limiter as rl
        original_limits = rl.DEFAULT_LIMITS.copy()
        rl.DEFAULT_LIMITS["api_write"] = 3

        try:
            for i in range(3):
                await chat(db, user_with_key, f"Message {i}", node.node_uid, [])

            with pytest.raises(RateLimited):
                await chat(db, user_with_key, "One too many", node.node_uid, [])
        finally:
            rl.DEFAULT_LIMITS.update(original_limits)
