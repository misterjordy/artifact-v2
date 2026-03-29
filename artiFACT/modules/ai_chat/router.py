"""AI Chat API endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.middleware import get_current_user
from artiFACT.kernel.db import get_db
from artiFACT.kernel.models import FcUser
from artiFACT.modules.ai_chat.context_provider import get_available_context
from artiFACT.modules.ai_chat.schemas import (
    AIKeyIn,
    AIKeyOut,
    AIStatusOut,
    ChatRequest,
    ChatResponse,
    ContextNode,
    ContextOut,
)
from artiFACT.modules.ai_chat.service import chat, chat_stream
from artiFACT.modules.auth_admin.ai_key_manager import (
    delete_ai_key,
    list_ai_keys,
    save_ai_key,
)

router = APIRouter(prefix="/api/v1/ai", tags=["ai_chat"])


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
    return StreamingResponse(stream, media_type="text/event-stream")


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


# --- AI Key CRUD (settings page) ---


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
