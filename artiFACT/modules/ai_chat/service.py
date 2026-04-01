"""Chat orchestration: load facts -> build prompt -> call AI -> filter -> stream."""

import json
import re
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.access_logger import log_data_access
from artiFACT.kernel.ai_provider import AIProvider
from artiFACT.kernel.events import publish
from artiFACT.kernel.exceptions import AppError
from artiFACT.kernel.models import FcNode, FcUser
from artiFACT.kernel.rate_limiter import check_rate
from artiFACT.modules.admin.anomaly_detector import check_anomaly
from artiFACT.modules.ai_chat.context_provider import get_facts_for_context
from artiFACT.modules.ai_chat.prompt_builder import build_system_prompt
from artiFACT.modules.ai_chat.retriever import (
    estimate_scope_tokens,
    load_all_facts,
    retrieve_relevant_facts,
)
from artiFACT.modules.ai_chat.safety.input_filter import check_input
from artiFACT.modules.ai_chat.safety.output_filter import check_output
from artiFACT.modules.ai_chat.session_manager import (
    get_messages,
    get_session,
    save_message,
)
from artiFACT.modules.auth_admin.ai_key_manager import get_ai_key

log = structlog.get_logger()

_ai = AIProvider()

_SEARCH_CMD = re.compile(r"^search\s+(?:for\s+)?(.+)$", re.IGNORECASE)


class NoAIKeyError(AppError):
    status_code = 400

    def __init__(self) -> None:
        super().__init__(
            detail="No AI API key configured. Add one in Settings.",
            code="NO_AI_KEY",
        )


# ── Legacy endpoints (backward compat) ──────────────────────────────


async def chat(
    db: AsyncSession,
    user: FcUser,
    message: str,
    node_uid: uuid.UUID | None,
    history: list[dict[str, str]],
) -> dict[str, Any]:
    """Non-streaming chat: returns full response dict (legacy endpoint)."""
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
        node = await db.get(FcNode, node_uid)
        if node:
            node_title = node.title

    system_prompt, facts_loaded = build_system_prompt(
        fact_sentences, program_name=node_title or "this"
    )

    if not input_check.clean:
        system_prompt += (
            "\n\n[CANARY: User input was flagged for: "
            + ", ".join(input_check.flags) + "]"
        )

    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": input_check.normalized})

    response_text = await _ai.complete_for_key(key_row, messages)

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

    await log_data_access(
        db, user.user_uid, "ai_chat",
        {"topic": node_title, "facts_loaded": facts_loaded},
    )
    await check_anomaly(db, user.user_uid, "ai_chat")

    key_row.last_used_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "content": filtered,
        "facts_loaded": facts_loaded,
        "facts_total": facts_total or facts_loaded,
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
    """Streaming chat: yields SSE-formatted chunks (legacy endpoint)."""
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
        node = await db.get(FcNode, node_uid)
        if node:
            node_title = node.title

    system_prompt, facts_loaded = build_system_prompt(
        fact_sentences, program_name=node_title or "this"
    )

    if not input_check.clean:
        system_prompt += (
            "\n\n[CANARY: User input was flagged for: "
            + ", ".join(input_check.flags) + "]"
        )

    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": input_check.normalized})

    meta = json.dumps({
        "facts_loaded": facts_loaded,
        "facts_total": facts_total or facts_loaded,
        "node_title": node_title,
        "flagged": not input_check.clean,
    })
    yield f"data: {json.dumps({'type': 'meta', 'data': json.loads(meta)})}\n\n"

    collected = ""
    stream_iter = await _ai.stream_for_key(key_row, messages)
    async for chunk in stream_iter:
        collected += chunk
        yield f"data: {json.dumps({'type': 'chunk', 'data': chunk})}\n\n"

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


# ── Session-based chat (new widget) ─────────────────────────────────


async def chat_with_session(
    db: AsyncSession,
    chat_uid: uuid.UUID,
    user_message: str,
    user: FcUser,
) -> AsyncIterator[str]:
    """Send a message in an existing chat session. Streams response via SSE.

    1. Load session (mode, constraints, fact_filter)
    2. Save user message
    3. Load facts (smart vs efficient)
    4. Build system prompt + conversation history
    5. Stream AI response, save assistant message
    6. Update session token totals
    """
    session = await get_session(db, chat_uid, user.user_uid)

    await check_rate(str(user.user_uid), "api_write")

    key_row = await get_ai_key(db, user.user_uid)
    if not key_row:
        raise NoAIKeyError()

    input_check = check_input(user_message)

    # Save user message
    await save_message(db, chat_uid, "user", input_check.normalized)

    # Parse "search for X" command in efficient mode
    search_query = input_check.normalized
    match = _SEARCH_CMD.match(input_check.normalized)
    if match and session.mode == "efficient":
        search_query = match.group(1)

    # Load facts based on mode
    constraint_uids = (
        [uuid.UUID(u) for u in session.constraint_node_uids]
        if session.constraint_node_uids
        else None
    )

    if session.mode == "smart":
        facts = await load_all_facts(
            db, session.program_node_uid, constraint_uids, session.fact_filter
        )
    else:
        facts = await retrieve_relevant_facts(
            db, search_query, session.program_node_uid,
            constraint_uids, session.fact_filter,
        )

    # Get total facts in scope for coverage note
    scope_info = await estimate_scope_tokens(
        db, session.program_node_uid, constraint_uids, session.fact_filter
    )

    # Get program name
    program_node = await db.get(FcNode, session.program_node_uid)
    program_name = program_node.title if program_node else "this"

    # Build system prompt
    system_prompt, facts_loaded = build_system_prompt(
        facts,
        program_name=program_name,
        mode=session.mode,
        total_facts_in_scope=scope_info["fact_count"],
    )

    if not input_check.clean:
        system_prompt += (
            "\n\n[CANARY: User input was flagged for: "
            + ", ".join(input_check.flags) + "]"
        )

    # Build conversation: system prompt + prior messages + current user message
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    prior = await get_messages(db, chat_uid)
    for msg in prior:
        if msg.role in ("user", "assistant"):
            messages.append({"role": msg.role, "content": msg.content})

    # Stream AI response
    collected = ""
    stream_iter = await _ai.stream_for_key(key_row, messages)
    async for chunk in stream_iter:
        collected += chunk
        yield f"data: {json.dumps({'chunk': chunk})}\n\n"

    # Output filter
    fact_sentences = [f["sentence"] if isinstance(f, dict) else f for f in facts]
    is_safe, filtered = check_output(collected, fact_sentences[:facts_loaded])
    if not is_safe:
        collected = filtered
        yield f"data: {json.dumps({'replace': filtered})}\n\n"

    # Estimate tokens (rough: 4 chars per token)
    input_tokens = len(system_prompt + input_check.normalized) // 4
    output_tokens = len(collected) // 4

    # Save assistant message
    await save_message(
        db, chat_uid, "assistant", collected,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        facts_loaded=facts_loaded,
    )

    # Update key last_used_at
    key_row.last_used_at = datetime.now(timezone.utc)
    await db.flush()

    # Final done event
    session_refreshed = await get_session(db, chat_uid, user.user_uid)
    yield f"data: {json.dumps({'done': True, 'input_tokens': input_tokens, 'output_tokens': output_tokens, 'facts_loaded': facts_loaded, 'session_total_tokens': session_refreshed.total_input_tokens + session_refreshed.total_output_tokens})}\n\n"

    await publish(
        "ai.chat",
        {
            "user_uid": str(user.user_uid),
            "provider": key_row.provider,
            "node_uid": str(session.program_node_uid),
            "flagged": not input_check.clean,
        },
    )

    await log_data_access(
        db, user.user_uid, "ai_chat",
        {"topic": program_name, "facts_loaded": facts_loaded},
    )
    await check_anomaly(db, user.user_uid, "ai_chat")
