"""Chat orchestration: load facts -> build prompt -> call AI -> filter -> stream."""

import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.access_logger import log_data_access
from artiFACT.kernel.ai_provider import AIProvider
from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import AppError
from artiFACT.kernel.models import FcUser
from artiFACT.kernel.rate_limiter import check_rate
from artiFACT.modules.admin.anomaly_detector import check_anomaly
from artiFACT.modules.ai_chat.context_provider import get_facts_for_context
from artiFACT.modules.ai_chat.prompt_builder import build_system_prompt
from artiFACT.modules.ai_chat.safety.input_filter import check_input
from artiFACT.modules.ai_chat.safety.output_filter import check_output
from artiFACT.modules.auth_admin.ai_key_manager import get_ai_key

_ai = AIProvider()


class NoAIKeyError(AppError):
    status_code = 400

    def __init__(self) -> None:
        super().__init__(
            detail="No AI API key configured. Add one in Settings.",
            code="NO_AI_KEY",
        )


async def chat(
    db: AsyncSession,
    user: FcUser,
    message: str,
    node_uid: uuid.UUID | None,
    history: list[dict[str, str]],
) -> dict[str, Any]:
    """Non-streaming chat: returns full response dict."""
    await check_rate(str(user.user_uid), "api_write")

    # Get user's AI key
    key_row = await get_ai_key(db, user.user_uid)
    if not key_row:
        raise NoAIKeyError()

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
    response_text = await _ai.complete_for_key(key_row, messages)

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
    history: list[dict[str, str]],
) -> AsyncIterator[str]:
    """Streaming chat: yields SSE-formatted chunks."""
    await check_rate(str(user.user_uid), "api_write")

    key_row = await get_ai_key(db, user.user_uid)
    if not key_row:
        raise NoAIKeyError()

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
    stream_iter = await _ai.stream_for_key(key_row, messages)
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


