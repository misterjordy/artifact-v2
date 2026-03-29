"""Chat orchestration: load facts -> build prompt -> call AI -> filter -> stream."""

import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.access_logger import log_data_access
from artiFACT.kernel.crypto import decrypt
from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import AppError
from artiFACT.kernel.models import FcUser, FcUserAiKey
from artiFACT.kernel.rate_limiter import check_rate
from artiFACT.modules.admin.anomaly_detector import check_anomaly
from artiFACT.modules.ai_chat.context_provider import get_facts_for_context
from artiFACT.modules.ai_chat.prompt_builder import build_system_prompt
from artiFACT.modules.ai_chat.safety.input_filter import check_input
from artiFACT.modules.ai_chat.safety.output_filter import check_output
from artiFACT.modules.auth_admin.ai_key_manager import get_ai_key


class NoAIKeyError(AppError):
    status_code = 400

    def __init__(self) -> None:
        super().__init__(
            detail="No AI API key configured. Add one in Settings.",
            code="NO_AI_KEY",
        )


DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
}


async def chat(
    db: AsyncSession,
    user: FcUser,
    message: str,
    node_uid: uuid.UUID | None,
    history: list[dict],
) -> dict:
    """Non-streaming chat: returns full response dict."""
    await check_rate(str(user.user_uid), "api_write")

    # Get user's AI key
    key_row = await get_ai_key(db, user.user_uid)
    if not key_row:
        raise NoAIKeyError()

    plaintext_key = decrypt(key_row.encrypted_key)

    # Input filter (Layer 1)
    input_check = check_input(message)

    # Load context facts
    fact_sentences: list[str] = []
    facts_total = 0
    node_title: str | None = None
    if node_uid:
        fact_sentences, facts_total = await get_facts_for_context(db, user, node_uid)
        from artiFACT.kernel.models import FcNode

        node = await db.get(FcNode, node_uid)
        if node:
            node_title = node.title

    # Build prompt (Layer 2 hardening built into header)
    system_prompt, facts_loaded, facts_total = build_system_prompt(fact_sentences, max_tokens=6000)

    # Add canary if input was flagged
    if not input_check.clean:
        system_prompt += (
            "\n\n[CANARY: User input was flagged for: " + ", ".join(input_check.flags) + "]"
        )

    # Build messages
    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": input_check.normalized})

    # Call AI provider
    response_text = await _call_provider(key_row, plaintext_key, messages, stream=False)

    # Output filter (Layer 3)
    is_safe, filtered = check_output(response_text, fact_sentences[:facts_loaded])

    await publish(
        "ai.chat",
        {
            "user_uid": str(user.user_uid),
            "provider": key_row.provider,
            "node_uid": str(node_uid) if node_uid else None,
            "flagged": not input_check.clean,
        },
    )

    # ZT Pillar 5: log data access
    await log_data_access(
        db,
        user.user_uid,
        "ai_chat",
        {
            "topic": node_title,
            "facts_loaded": facts_loaded,
        },
    )
    await check_anomaly(db, user.user_uid, "ai_chat")

    # Update last_used_at
    key_row.last_used_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "content": filtered,
        "facts_loaded": facts_loaded,
        "facts_total": facts_total,
        "node_title": node_title,
        "flagged": not input_check.clean,
    }


async def chat_stream(
    db: AsyncSession,
    user: FcUser,
    message: str,
    node_uid: uuid.UUID | None,
    history: list[dict],
) -> AsyncIterator[str]:
    """Streaming chat: yields SSE-formatted chunks."""
    await check_rate(str(user.user_uid), "api_write")

    key_row = await get_ai_key(db, user.user_uid)
    if not key_row:
        raise NoAIKeyError()

    plaintext_key = decrypt(key_row.encrypted_key)

    input_check = check_input(message)

    fact_sentences: list[str] = []
    facts_total = 0
    node_title: str | None = None
    if node_uid:
        fact_sentences, facts_total = await get_facts_for_context(db, user, node_uid)
        from artiFACT.kernel.models import FcNode

        node = await db.get(FcNode, node_uid)
        if node:
            node_title = node.title

    system_prompt, facts_loaded, facts_total = build_system_prompt(fact_sentences, max_tokens=6000)

    if not input_check.clean:
        system_prompt += (
            "\n\n[CANARY: User input was flagged for: " + ", ".join(input_check.flags) + "]"
        )

    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": input_check.normalized})

    # Send metadata first
    meta = json.dumps(
        {
            "facts_loaded": facts_loaded,
            "facts_total": facts_total,
            "node_title": node_title,
            "flagged": not input_check.clean,
        }
    )
    yield f"data: {json.dumps({'type': 'meta', 'data': json.loads(meta)})}\n\n"

    # Stream response chunks
    collected = ""
    stream_iter = await _call_provider(key_row, plaintext_key, messages, stream=True)
    async for chunk in stream_iter:
        collected += chunk
        yield f"data: {json.dumps({'type': 'chunk', 'data': chunk})}\n\n"

    # Output filter on complete response
    is_safe, filtered = check_output(collected, fact_sentences[:facts_loaded])
    if not is_safe:
        yield f"data: {json.dumps({'type': 'replace', 'data': filtered})}\n\n"

    yield "data: [DONE]\n\n"

    key_row.last_used_at = datetime.now(timezone.utc)
    await db.flush()

    await publish(
        "ai.chat",
        {
            "user_uid": str(user.user_uid),
            "provider": key_row.provider,
            "node_uid": str(node_uid) if node_uid else None,
            "flagged": not input_check.clean,
        },
    )


async def _call_provider(
    key_row: FcUserAiKey,
    plaintext_key: str,
    messages: list[dict],
    *,
    stream: bool = False,
    timeout: int = 120,
    max_tokens: int = 4096,
) -> str | AsyncIterator[str]:
    """Route to correct provider's API."""
    provider = key_row.provider
    model = key_row.model_override or DEFAULT_MODELS.get(provider, "gpt-4o")

    if provider == "openai" or provider == "azure_openai":
        return await _call_openai(plaintext_key, messages, model, stream, timeout, max_tokens)
    elif provider == "anthropic":
        return await _call_anthropic(plaintext_key, messages, model, stream, timeout, max_tokens)
    else:
        raise AppError(f"Unsupported provider: {provider}")


async def _call_openai(
    api_key: str,
    messages: list[dict],
    model: str,
    stream: bool,
    timeout: int,
    max_tokens: int,
) -> str | AsyncIterator[str]:
    """Call OpenAI chat completions API."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": stream,
    }

    if stream:
        return _stream_openai(headers, body, timeout)

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _stream_openai(
    headers: dict,
    body: dict,
    timeout: int,
) -> AsyncIterator[str]:
    """Stream OpenAI response chunks."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=body,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    payload = line[6:]
                    if payload == "[DONE]":
                        break
                    chunk_data = json.loads(payload)
                    delta = chunk_data["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content


async def _call_anthropic(
    api_key: str,
    messages: list[dict],
    model: str,
    stream: bool,
    timeout: int,
    max_tokens: int,
) -> str | AsyncIterator[str]:
    """Call Anthropic messages API."""
    # Extract system message from messages list
    system_content = ""
    api_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_content = msg["content"]
        else:
            api_messages.append(msg)

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_content,
        "messages": api_messages,
        "stream": stream,
    }

    if stream:
        return _stream_anthropic(headers, body, timeout)

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]


async def _stream_anthropic(
    headers: dict,
    body: dict,
    timeout: int,
) -> AsyncIterator[str]:
    """Stream Anthropic response chunks."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
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
