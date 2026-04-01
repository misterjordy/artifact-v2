"""Chat session CRUD — persistent chat history in PostgreSQL."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.exceptions import NotFound
from artiFACT.kernel.models import FcChatMessage, FcChatSession


async def create_session(
    db: AsyncSession,
    user_uid: uuid.UUID,
    program_node_uid: uuid.UUID,
    constraint_node_uids: list[uuid.UUID] | None = None,
    mode: str = "efficient",
    fact_filter: str = "published",
) -> FcChatSession:
    """Create a new chat session. Does not send any messages."""
    session = FcChatSession(
        chat_uid=uuid.uuid4(),
        user_uid=user_uid,
        program_node_uid=program_node_uid,
        constraint_node_uids=[str(u) for u in constraint_node_uids] if constraint_node_uids else [],
        mode=mode,
        fact_filter=fact_filter,
    )
    db.add(session)
    await db.flush()
    return session


async def get_active_sessions(
    db: AsyncSession,
    user_uid: uuid.UUID,
) -> list[FcChatSession]:
    """Return all active chat sessions for this user, newest first."""
    result = await db.execute(
        select(FcChatSession)
        .where(FcChatSession.user_uid == user_uid, FcChatSession.is_active.is_(True))
        .order_by(FcChatSession.created_at.desc())
    )
    return list(result.scalars().all())


async def get_session(
    db: AsyncSession,
    chat_uid: uuid.UUID,
    user_uid: uuid.UUID,
) -> FcChatSession:
    """Get a session. Raises NotFound if missing or not owned by user."""
    result = await db.execute(
        select(FcChatSession).where(
            FcChatSession.chat_uid == chat_uid,
            FcChatSession.user_uid == user_uid,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise NotFound("Chat session not found", code="CHAT_SESSION_NOT_FOUND")
    return session


async def close_session(
    db: AsyncSession,
    chat_uid: uuid.UUID,
    user_uid: uuid.UUID,
) -> None:
    """Set is_active=False, DELETE all messages. Session record kept for token tracking."""
    session = await get_session(db, chat_uid, user_uid)
    session.is_active = False
    await db.execute(
        delete(FcChatMessage).where(FcChatMessage.chat_uid == chat_uid)
    )
    await db.flush()


async def update_fact_filter(
    db: AsyncSession,
    chat_uid: uuid.UUID,
    user_uid: uuid.UUID,
    fact_filter: str,
) -> FcChatSession:
    """Update the fact_filter on an active session."""
    session = await get_session(db, chat_uid, user_uid)
    session.fact_filter = fact_filter
    await db.flush()
    return session


async def save_message(
    db: AsyncSession,
    chat_uid: uuid.UUID,
    role: str,
    content: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    facts_loaded: int = 0,
) -> FcChatMessage:
    """Save a message and update session.last_message_at and token totals."""
    msg = FcChatMessage(
        message_uid=uuid.uuid4(),
        chat_uid=chat_uid,
        role=role,
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        facts_loaded=facts_loaded,
    )
    db.add(msg)
    await db.execute(
        update(FcChatSession)
        .where(FcChatSession.chat_uid == chat_uid)
        .values(
            last_message_at=datetime.now(timezone.utc),
            total_input_tokens=FcChatSession.total_input_tokens + input_tokens,
            total_output_tokens=FcChatSession.total_output_tokens + output_tokens,
        )
    )
    await db.flush()
    return msg


async def get_messages(
    db: AsyncSession,
    chat_uid: uuid.UUID,
) -> list[FcChatMessage]:
    """Return all messages for a session, ordered by created_at ASC."""
    result = await db.execute(
        select(FcChatMessage)
        .where(FcChatMessage.chat_uid == chat_uid)
        .order_by(FcChatMessage.created_at.asc())
    )
    return list(result.scalars().all())
