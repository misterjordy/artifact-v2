"""AI Chat API endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.db import get_db
from artiFACT.kernel.exceptions import NotFound
from artiFACT.kernel.models import FcChatMessage, FcChatSession, FcNode, FcUser
from artiFACT.modules.ai_chat.context_provider import get_available_context
from artiFACT.modules.ai_chat.retriever import estimate_scope_tokens
from artiFACT.modules.ai_chat.schemas import (
    AIKeyIn,
    AIKeyOut,
    AIStatusOut,
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    ChatSessionOut,
    ContextNode,
    ContextOut,
    CreateChatSession,
    SendMessage,
    TokenEstimate,
    UpdateFactFilter,
)
from artiFACT.modules.ai_chat.service import (
    chat,
    chat_stream,
    prepare_chat_session,
    stream_chat_response,
)
from artiFACT.modules.ai_chat.session_manager import (
    close_session,
    create_session,
    get_active_sessions,
    get_messages,
    get_session,
    update_fact_filter,
)
from artiFACT.modules.auth_admin.ai_key_manager import (
    delete_ai_key,
    list_ai_keys,
    save_ai_key,
)

router = APIRouter(prefix="/api/v1/ai", tags=["ai_chat"])


# ── Legacy endpoints (backward compat) ──────────────────────────────


@router.post("/chat", response_model=ChatResponse)
async def post_chat(
    body: ChatRequest,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Send a chat message, receive corpus-grounded response."""
    result = await chat(
        db=db,
        user=user,
        message=body.message,
        node_uid=body.node_uid,
        history=[h.model_dump() for h in body.history],
    )
    return ChatResponse(**result)


@router.post("/chat/stream")
async def post_chat_stream(
    body: ChatRequest,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Send a chat message, receive streaming SSE response."""
    stream = chat_stream(
        db=db,
        user=user,
        message=body.message,
        node_uid=body.node_uid,
        history=[h.model_dump() for h in body.history],
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@router.get("/context", response_model=ContextOut)
async def get_context(
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContextOut:
    """Available programs/topics scoped to user's readable nodes."""
    ctx = await get_available_context(db, user)
    programs = [ContextNode.model_validate(p) for p in ctx["programs"]]
    topics = {k: [ContextNode.model_validate(n) for n in v] for k, v in ctx["topics"].items()}
    return ContextOut(programs=programs, topics=topics)


@router.get("/status", response_model=AIStatusOut)
async def get_status(
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIStatusOut:
    """User's AI key status."""
    keys = await list_ai_keys(db, user.user_uid)
    return AIStatusOut(
        has_key=len(keys) > 0,
        keys=[AIKeyOut.model_validate(k) for k in keys],
    )


# ── AI Key CRUD (settings page) ─────────────────────────────────────


@router.post("/keys", response_model=AIKeyOut, status_code=201)
async def create_key(
    body: AIKeyIn,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIKeyOut:
    """Save or update an AI API key for the current user."""
    row = await save_ai_key(
        db=db,
        user_uid=user.user_uid,
        provider=body.provider,
        plaintext_key=body.api_key,
        model_override=body.model_override,
    )
    await db.commit()
    return AIKeyOut.model_validate(row)


@router.get("/keys", response_model=list[AIKeyOut])
async def list_keys(
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AIKeyOut]:
    """List all AI keys for current user (metadata only)."""
    keys = await list_ai_keys(db, user.user_uid)
    return [AIKeyOut.model_validate(k) for k in keys]


@router.delete("/keys/{provider}", status_code=204)
async def remove_key(
    provider: str,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an AI key by provider."""
    await delete_ai_key(db, user.user_uid, provider)
    await db.commit()


# ── Session-based chat (new widget) ─────────────────────────────────


@router.post("/chat/sessions", response_model=ChatSessionOut, status_code=201)
async def create_chat_session(
    body: CreateChatSession,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionOut:
    """Create a new chat session."""
    # Validate program node exists
    program = await db.get(FcNode, body.program_node_uid)
    if not program:
        raise NotFound("Program node not found", code="NODE_NOT_FOUND")

    session = await create_session(
        db=db,
        user_uid=user.user_uid,
        program_node_uid=body.program_node_uid,
        constraint_node_uids=body.constraint_node_uids,
        mode=body.mode,
        fact_filter=body.fact_filter,
    )

    # Resolve constraint names
    constraint_names: list[str] = []
    if body.constraint_node_uids:
        for uid in body.constraint_node_uids:
            node = await db.get(FcNode, uid)
            if node:
                constraint_names.append(node.title)

    await db.commit()

    return ChatSessionOut(
        chat_uid=session.chat_uid,
        program_name=program.title,
        constraint_names=constraint_names,
        mode=session.mode,
        fact_filter=session.fact_filter,
        message_count=0,
        total_input_tokens=0,
        total_output_tokens=0,
        created_at=session.created_at,
        last_message_at=session.last_message_at,
    )


@router.get("/chat/sessions", response_model=list[ChatSessionOut])
async def list_chat_sessions(
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatSessionOut]:
    """Return user's active sessions with metadata."""
    sessions = await get_active_sessions(db, user.user_uid)
    result: list[ChatSessionOut] = []
    for s in sessions:
        program = await db.get(FcNode, s.program_node_uid)
        program_name = program.title if program else "Unknown"

        constraint_names: list[str] = []
        if s.constraint_node_uids:
            for uid_str in s.constraint_node_uids:
                node = await db.get(FcNode, uuid.UUID(uid_str))
                if node:
                    constraint_names.append(node.title)

        msg_count_result = await db.execute(
            select(func.count()).where(FcChatMessage.chat_uid == s.chat_uid)
        )
        msg_count = msg_count_result.scalar() or 0

        result.append(ChatSessionOut(
            chat_uid=s.chat_uid,
            program_name=program_name,
            constraint_names=constraint_names,
            mode=s.mode,
            fact_filter=s.fact_filter,
            message_count=msg_count,
            total_input_tokens=s.total_input_tokens,
            total_output_tokens=s.total_output_tokens,
            created_at=s.created_at,
            last_message_at=s.last_message_at,
        ))
    return result


@router.delete("/chat/sessions/{chat_uid}", status_code=200)
async def delete_chat_session(
    chat_uid: uuid.UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Close a chat session (is_active=false, messages deleted)."""
    await close_session(db, chat_uid, user.user_uid)
    await db.commit()
    return {"status": "closed"}


@router.patch("/chat/sessions/{chat_uid}/filter", status_code=200)
async def patch_session_filter(
    chat_uid: uuid.UUID,
    body: UpdateFactFilter,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Update fact_filter on an active session (published/signed toggle)."""
    await update_fact_filter(db, chat_uid, user.user_uid, body.fact_filter)
    await db.commit()
    return {"status": "updated", "fact_filter": body.fact_filter}


@router.post("/chat/{chat_uid}/send", response_model=None)
async def send_chat_message(
    chat_uid: uuid.UUID,
    body: SendMessage,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message in a chat session. Streams response via SSE."""
    # All setup runs here — failures become proper HTTP errors (400/404/500)
    ctx = await prepare_chat_session(
        db=db,
        chat_uid=chat_uid,
        user_message=body.content,
        user=user,
        full_corpus=body.full_corpus,
    )

    # No-API-key: return static frame JSON instead of SSE stream
    if ctx.get("static_frame"):
        from artiFACT.modules.ai_chat.service import _build_static_frame

        return JSONResponse(content={"data": _build_static_frame(ctx)})

    # Only the AI streaming loop lives in the generator
    stream = stream_chat_response(db=db, chat_uid=chat_uid, user=user, ctx=ctx)
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@router.get("/chat/{chat_uid}/messages", response_model=list[ChatMessageOut])
async def get_chat_messages(
    chat_uid: uuid.UUID,
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessageOut]:
    """Return ordered messages for this session."""
    await get_session(db, chat_uid, user.user_uid)
    messages = await get_messages(db, chat_uid)
    return [ChatMessageOut.model_validate(m) for m in messages]


@router.get("/chat/estimate", response_model=TokenEstimate)
async def get_token_estimate(
    program_node_uid: uuid.UUID = Query(...),
    constraint_node_uids: str | None = Query(default=None),
    fact_filter: str = Query(default="published", pattern="^(published|signed)$"),
    user: FcUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TokenEstimate:
    """Estimate token cost for a given scope."""
    parsed_constraints: list[uuid.UUID] | None = None
    if constraint_node_uids:
        parsed_constraints = [uuid.UUID(u.strip()) for u in constraint_node_uids.split(",")]

    result = await estimate_scope_tokens(
        db, program_node_uid, parsed_constraints, fact_filter
    )
    return TokenEstimate(**result)
