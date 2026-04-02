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
from artiFACT.modules.ai_chat.intent_mapper import enrich_query_with_context
from artiFACT.modules.ai_chat.retriever import (
    _get_scope_node_uids,
    estimate_scope_tokens,
    load_all_facts,
    retrieve_facts,
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
    await db.commit()

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
    await db.commit()

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


async def prepare_chat_session(
    db: AsyncSession,
    chat_uid: uuid.UUID,
    user_message: str,
    user: FcUser,
    *,
    full_corpus: bool = False,
) -> dict:
    """Do all setup work for a chat session message.

    This runs BEFORE the StreamingResponse is created, so any failure
    becomes a proper HTTP error instead of a broken stream.

    Uses unified BM25 retrieval by default, or loads all facts when
    full_corpus=True.

    Returns a dict with everything the streaming generator needs.
    """
    session = await get_session(db, chat_uid, user.user_uid)

    await check_rate(str(user.user_uid), "api_write")

    key_row = await get_ai_key(db, user.user_uid)

    input_check = check_input(user_message)

    # Save user message and commit so the row lock is released before streaming
    await save_message(db, chat_uid, "user", input_check.normalized)
    await db.commit()

    # Resolve scope
    constraint_uids = (
        [uuid.UUID(u) for u in session.constraint_node_uids]
        if session.constraint_node_uids
        else None
    )
    scope_node_uids = await _get_scope_node_uids(
        db, session.program_node_uid, constraint_uids
    )

    # Get program name
    program_node = await db.get(FcNode, session.program_node_uid)
    program_name = program_node.title if program_node else "this"

    # Load facts: full corpus or BM25 retrieval
    if full_corpus:
        facts = await load_all_facts(db, scope_node_uids)
    else:
        # Parse "search for X" command
        search_query = input_check.normalized
        match = _SEARCH_CMD.match(input_check.normalized)
        if match:
            search_query = match.group(1)

        # Enrich with conversational context
        enriched = enrich_query_with_context(
            search_query, None, program_name,
        )
        facts = await retrieve_facts(db, enriched, scope_node_uids)

    # Get total facts in scope for coverage note
    scope_info = await estimate_scope_tokens(
        db, session.program_node_uid, constraint_uids, session.fact_filter
    )

    # No-API-key static frame
    if not key_row:
        return {
            "static_frame": True,
            "facts": facts[:4],
            "scope_info": scope_info,
            "program_name": program_name,
            "input_check": input_check,
        }

    # Build system prompt
    system_prompt, facts_loaded = build_system_prompt(
        facts,
        program_name=program_name,
        total_facts_in_scope=scope_info["fact_count"],
    )

    if not input_check.clean:
        system_prompt += (
            "\n\n[CANARY: User input was flagged for: "
            + ", ".join(input_check.flags) + "]"
        )

    # Build conversation: system prompt + last 20 messages as context
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    prior = await get_messages(db, chat_uid)
    for msg in prior[-20:]:
        if msg.role in ("user", "assistant"):
            messages.append({"role": msg.role, "content": msg.content})

    return {
        "session": session,
        "key_row": key_row,
        "input_check": input_check,
        "messages": messages,
        "facts": facts,
        "facts_loaded": facts_loaded,
        "system_prompt": system_prompt,
        "program_name": program_name,
        "scope_info": scope_info,
    }


async def stream_chat_response(
    db: AsyncSession,
    chat_uid: uuid.UUID,
    user: FcUser,
    ctx: dict,
) -> AsyncIterator[str]:
    """Stream AI response for a prepared chat session.

    Only the actual AI call + post-stream save lives in the generator.
    All setup that can fail is done in prepare_chat_session() before
    the StreamingResponse is created.
    """
    session = ctx["session"]
    key_row = ctx["key_row"]
    input_check = ctx["input_check"]
    messages = ctx["messages"]
    facts = ctx["facts"]
    facts_loaded = ctx["facts_loaded"]
    system_prompt = ctx["system_prompt"]
    program_name = ctx["program_name"]
    scope_info = ctx.get("scope_info", {})

    # Stream AI response — catch provider errors (429, 500, etc.)
    collected = ""
    try:
        stream_iter = await _ai.stream_for_key(key_row, messages)
        async for chunk in stream_iter:
            collected += chunk
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
    except Exception as exc:
        log.exception("ai_stream_error", chat_uid=str(chat_uid), error=str(exc))
        exc_str = str(exc)
        if "insufficient_quota" in exc_str or "billing" in exc_str.lower():
            error_msg = "Your OpenAI API key has no remaining quota. Check your billing at platform.openai.com."
        elif "429" in exc_str:
            error_msg = "Rate limit reached. Wait a moment and try again."
        elif "401" in exc_str or "invalid" in exc_str.lower():
            error_msg = "Your AI API key is invalid. Update it in Settings."
        else:
            error_msg = "AI provider error. Please try again."
        yield f"data: {json.dumps({'chunk': error_msg})}\n\n"
        yield f"data: {json.dumps({'done': True, 'input_tokens': 0, 'output_tokens': 0, 'facts_loaded': 0, 'session_total_tokens': 0})}\n\n"
        return

    # Output filter — extract sentences from ScoredFact or dict or str
    fact_sentences = []
    for f in facts:
        if isinstance(f, str):
            fact_sentences.append(f)
        elif isinstance(f, dict):
            fact_sentences.append(f.get("sentence", ""))
        else:
            fact_sentences.append(f.display_sentence)
    is_safe, filtered = check_output(collected, fact_sentences[:facts_loaded])
    if not is_safe:
        collected = filtered
        yield f"data: {json.dumps({'replace': filtered})}\n\n"

    # Estimate tokens (rough: 4 chars per token)
    input_tokens = len(system_prompt + input_check.normalized) // 4
    output_tokens = len(collected) // 4

    # Save assistant message + finalize — errors here must not kill the stream
    try:
        await save_message(
            db, chat_uid, "assistant", collected,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            facts_loaded=facts_loaded,
        )

        key_row.last_used_at = datetime.now(timezone.utc)
        await db.commit()

        session_refreshed = await get_session(db, chat_uid, user.user_uid)
        done_payload = {
            "done": True,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "facts_loaded": facts_loaded,
            "session_total_tokens": (
                session_refreshed.total_input_tokens
                + session_refreshed.total_output_tokens
            ),
            "scope_fact_count": scope_info.get("fact_count", 0),
            "loaded_fact_count": facts_loaded,
            "full_corpus_token_estimate": scope_info.get(
                "full_corpus_token_estimate", 0
            ),
        }
        yield f"data: {json.dumps(done_payload)}\n\n"

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
    except Exception:
        log.exception("post-stream save failed", chat_uid=str(chat_uid))
        yield f"data: {json.dumps({'done': True, 'input_tokens': 0, 'output_tokens': 0, 'facts_loaded': 0, 'session_total_tokens': 0})}\n\n"


async def chat_with_session(
    db: AsyncSession,
    chat_uid: uuid.UUID,
    user_message: str,
    user: FcUser,
    *,
    full_corpus: bool = False,
) -> AsyncIterator[str]:
    """Convenience wrapper: prepare + stream in one async generator (used by tests)."""
    ctx = await prepare_chat_session(
        db, chat_uid, user_message, user, full_corpus=full_corpus,
    )
    if ctx.get("static_frame"):
        yield json.dumps(_build_static_frame(ctx))
        return
    async for chunk in stream_chat_response(db, chat_uid, user, ctx):
        yield chunk


def _build_static_frame(ctx: dict) -> dict:
    """Build no-API-key static frame response."""
    facts = ctx.get("facts", [])
    return {
        "type": "static_frame",
        "message": (
            "I found these potentially relevant facts, but without "
            "an AI key I can't synthesize an answer:"
        ),
        "facts": [
            {
                "sentence": f.display_sentence if hasattr(f, "display_sentence") else str(f),
                "score": round(f.blended_score, 2) if hasattr(f, "blended_score") else 0,
            }
            for f in facts
        ],
        "action": {
            "label": "Add AI key in Settings",
            "url": "/settings#ai-key",
        },
        "token_count": 0,
    }
