"""Shared AI provider abstraction — routes LLM calls by user's configured provider."""

import json
from collections.abc import AsyncIterator
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from artiFACT.kernel.crypto import decrypt
from artiFACT.kernel.models import FcUserAiKey

log = structlog.get_logger()

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
}


class AIProvider:
    """Single abstraction for all LLM calls. Handles key lookup, decryption, provider routing."""

    # --- High-level: auto key lookup ---

    async def complete(
        self,
        db: AsyncSession,
        user_uid: UUID,
        messages: list[dict],
        *,
        response_format: dict | None = None,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> str:
        """Async LLM completion — looks up user's key and routes to correct provider."""
        key_row = await self._get_key(db, user_uid)
        return await self.complete_for_key(
            key_row, messages,
            response_format=response_format,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    # --- Mid-level: caller provides key_row ---

    async def complete_for_key(
        self,
        key_row: FcUserAiKey,
        messages: list[dict],
        *,
        response_format: dict | None = None,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> str:
        """Async completion with a pre-fetched key row. Handles decrypt + routing."""
        plaintext_key = decrypt(key_row.encrypted_key)
        provider = key_row.provider
        model = key_row.model_override or DEFAULT_MODELS.get(provider, "gpt-4o")

        if provider in ("openai", "azure_openai"):
            return await self._async_openai(
                plaintext_key, model, messages, response_format, max_tokens, timeout,
            )
        elif provider == "anthropic":
            return await self._async_anthropic(
                plaintext_key, model, messages, max_tokens, timeout,
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    async def stream_for_key(
        self,
        key_row: FcUserAiKey,
        messages: list[dict],
        *,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> AsyncIterator[str]:
        """Async streaming with a pre-fetched key row. Yields text chunks."""
        plaintext_key = decrypt(key_row.encrypted_key)
        provider = key_row.provider
        model = key_row.model_override or DEFAULT_MODELS.get(provider, "gpt-4o")

        if provider in ("openai", "azure_openai"):
            return self._stream_openai(plaintext_key, model, messages, max_tokens, timeout)
        elif provider == "anthropic":
            return self._stream_anthropic(plaintext_key, model, messages, max_tokens, timeout)
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
    ) -> str:
        """Sync LLM completion for Celery tasks."""
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
        elif provider == "anthropic":
            return self._sync_anthropic(
                plaintext_key, model, messages, max_tokens, timeout,
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
    ) -> str:
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
        return str(resp.json()["choices"][0]["message"]["content"])

    # --- OpenAI (async, streaming) ---

    async def _stream_openai(
        self,
        api_key: str,
        model: str,
        messages: list[dict],
        max_tokens: int,
        timeout: int,
    ) -> AsyncIterator[str]:
        body = {"model": model, "messages": messages, "max_tokens": max_tokens, "stream": True}
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
                        content = chunk_data["choices"][0].get("delta", {}).get("content", "")
                        if content:
                            yield content

    # --- Anthropic (async, non-streaming) ---

    async def _async_anthropic(
        self,
        api_key: str,
        model: str,
        messages: list[dict],
        max_tokens: int,
        timeout: int,
    ) -> str:
        system_content, api_messages = self._split_system(messages)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "system": system_content,
                    "messages": api_messages,
                },
            )
            resp.raise_for_status()
        return str(resp.json()["content"][0]["text"])

    # --- Anthropic (async, streaming) ---

    async def _stream_anthropic(
        self,
        api_key: str,
        model: str,
        messages: list[dict],
        max_tokens: int,
        timeout: int,
    ) -> AsyncIterator[str]:
        system_content, api_messages = self._split_system(messages)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "system": system_content,
                    "messages": api_messages,
                    "stream": True,
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        payload = line[6:]
                        chunk_data = json.loads(payload)
                        if chunk_data.get("type") == "content_block_delta":
                            text = chunk_data.get("delta", {}).get("text", "")
                            if text:
                                yield text

    # --- OpenAI (sync) ---

    def _sync_openai(
        self, api_key: str, model: str, messages: list[dict],
        response_format: dict | None, max_tokens: int, timeout: int,
    ) -> str:
        body: dict = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if response_format:
            body["response_format"] = response_format
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body, timeout=timeout,
        )
        resp.raise_for_status()
        return str(resp.json()["choices"][0]["message"]["content"])

    # --- Anthropic (sync) ---

    def _sync_anthropic(
        self, api_key: str, model: str, messages: list[dict],
        max_tokens: int, timeout: int,
    ) -> str:
        system_content, api_messages = self._split_system(messages)
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model, "max_tokens": max_tokens,
                "system": system_content, "messages": api_messages,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return str(resp.json()["content"][0]["text"])

    # --- Utility ---

    @staticmethod
    def _split_system(messages: list[dict]) -> tuple[str, list[dict]]:
        """Extract system message from messages list (Anthropic API format)."""
        system_content = ""
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                api_messages.append(msg)
        return system_content, api_messages
