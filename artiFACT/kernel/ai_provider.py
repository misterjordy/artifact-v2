"""Shared AI provider abstraction — routes LLM calls by user's configured provider."""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from artiFACT.kernel.crypto import decrypt
from artiFACT.kernel.models import FcAiUsage, FcUserAiKey

log = structlog.get_logger()

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o",
}

_COST_PER_1M: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
}


@dataclass
class AIUsage:
    """Token usage from an LLM API call."""

    input_tokens: int = 0
    output_tokens: int = 0
    is_actual: bool = False

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost from token counts."""
    rates = _COST_PER_1M.get(model, {"input": 3.0, "output": 10.0})
    return round(
        (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000,
        6,
    )


async def record_ai_usage(
    db: AsyncSession,
    user_uid: UUID,
    provider: str,
    model: str,
    usage: AIUsage,
    action: str,
) -> None:
    """Record AI token usage. Prefers actual counts from the API."""
    db.add(FcAiUsage(
        user_uid=user_uid,
        provider=provider,
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        estimated_cost=_compute_cost(model, usage.input_tokens, usage.output_tokens),
        action=action,
    ))


class AIProvider:
    """Single abstraction for all LLM calls.

    Supported providers: openai, azure_openai.
    Future: bedrock (COSMOS IAM-based, no user key).
    """

    def __init__(self) -> None:
        self.last_usage: AIUsage = AIUsage()

    # --- High-level: auto key lookup + usage recording ---

    async def complete(
        self,
        db: AsyncSession,
        user_uid: UUID,
        messages: list[dict],
        *,
        response_format: dict | None = None,
        max_tokens: int = 4096,
        timeout: int = 120,
        action: str = "ai_complete",
    ) -> tuple[str, AIUsage]:
        """Async LLM completion — looks up key, routes, records usage.

        Returns (content, usage).
        """
        key_row = await self._get_key(db, user_uid)
        content, usage = await self.complete_for_key(
            key_row, messages,
            response_format=response_format,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        provider = key_row.provider
        model = key_row.model_override or DEFAULT_MODELS.get(provider, "gpt-4o")
        await record_ai_usage(db, user_uid, provider, model, usage, action)
        return content, usage

    # --- Mid-level: caller provides key_row ---

    async def complete_for_key(
        self,
        key_row: FcUserAiKey,
        messages: list[dict],
        *,
        response_format: dict | None = None,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> tuple[str, AIUsage]:
        """Async completion with a pre-fetched key row. Returns (content, usage)."""
        plaintext_key = decrypt(key_row.encrypted_key)
        provider = key_row.provider
        model = key_row.model_override or DEFAULT_MODELS.get(provider, "gpt-4o")

        if provider in ("openai", "azure_openai"):
            content, usage = await self._async_openai(
                plaintext_key, model, messages, response_format, max_tokens, timeout,
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        self.last_usage = usage
        return content, usage

    async def stream_for_key(
        self,
        key_row: FcUserAiKey,
        messages: list[dict],
        *,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> tuple[AsyncIterator[str], AIUsage]:
        """Async streaming. Returns (iterator, usage).

        Usage is populated after the stream is fully consumed.
        """
        plaintext_key = decrypt(key_row.encrypted_key)
        provider = key_row.provider
        model = key_row.model_override or DEFAULT_MODELS.get(provider, "gpt-4o")

        self.last_usage = AIUsage()

        if provider in ("openai", "azure_openai"):
            return await self._stream_openai(
                plaintext_key, model, messages, max_tokens, timeout,
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    # --- Sync (Celery tasks) ---

    def complete_sync(
        self,
        db: Session,
        user_uid: UUID,
        messages: list[dict],
        *,
        response_format: dict | None = None,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> tuple[str, AIUsage]:
        """Sync LLM completion for Celery tasks. Returns (content, usage)."""
        key_row = db.execute(
            select(FcUserAiKey).where(FcUserAiKey.user_uid == user_uid)
        ).scalar_one_or_none()
        if not key_row:
            raise RuntimeError("No AI key configured for user")

        plaintext_key = decrypt(key_row.encrypted_key)
        provider = key_row.provider
        model = key_row.model_override or DEFAULT_MODELS.get(provider, "gpt-4o")

        if provider in ("openai", "azure_openai"):
            return self._sync_openai(
                plaintext_key, model, messages, response_format, max_tokens, timeout,
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    # --- Internal helpers ---

    async def _get_key(self, db: AsyncSession, user_uid: UUID) -> FcUserAiKey:
        key_row = (
            await db.execute(
                select(FcUserAiKey).where(FcUserAiKey.user_uid == user_uid)
            )
        ).scalar_one_or_none()
        if not key_row:
            raise RuntimeError("No AI key configured for user")
        return key_row

    # --- OpenAI (async, non-streaming) ---

    async def _async_openai(
        self,
        api_key: str,
        model: str,
        messages: list[dict],
        response_format: dict | None,
        max_tokens: int,
        timeout: int,
    ) -> tuple[str, AIUsage]:
        body: dict = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if response_format:
            body["response_format"] = response_format

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
            )
            resp.raise_for_status()
        data = resp.json()
        usage_data = data.get("usage", {})
        usage = AIUsage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
            is_actual=bool(usage_data),
        )
        return str(data["choices"][0]["message"]["content"]), usage

    # --- OpenAI (async, streaming) ---

    async def _stream_openai(
        self,
        api_key: str,
        model: str,
        messages: list[dict],
        max_tokens: int,
        timeout: int,
    ) -> tuple[AsyncIterator[str], AIUsage]:
        body: dict = {
            "model": model, "messages": messages, "max_tokens": max_tokens,
            "stream": True, "stream_options": {"include_usage": True},
        }
        usage = AIUsage()

        async def _generate() -> AsyncIterator[str]:
            nonlocal usage
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=body,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            payload = line[6:]
                            if payload == "[DONE]":
                                break
                            chunk_data = json.loads(payload)
                            if chunk_data.get("usage"):
                                u = chunk_data["usage"]
                                usage.input_tokens = u.get("prompt_tokens", 0)
                                usage.output_tokens = u.get("completion_tokens", 0)
                                usage.is_actual = True
                            choices = chunk_data.get("choices", [])
                            if choices:
                                content = choices[0].get("delta", {}).get("content", "")
                                if content:
                                    yield content
            self.last_usage = usage

        return _generate(), usage

    # --- OpenAI (sync) ---

    def _sync_openai(
        self, api_key: str, model: str, messages: list[dict],
        response_format: dict | None, max_tokens: int, timeout: int,
    ) -> tuple[str, AIUsage]:
        body: dict = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if response_format:
            body["response_format"] = response_format
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body, timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        usage_data = data.get("usage", {})
        usage = AIUsage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
            is_actual=bool(usage_data),
        )
        self.last_usage = usage
        return str(data["choices"][0]["message"]["content"]), usage

    # --- Utility ---

    @staticmethod
    def _split_system(messages: list[dict]) -> tuple[str, list[dict]]:
        """Extract system message from messages list."""
        system_content = ""
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                api_messages.append(msg)
        return system_content, api_messages
