"""FastAPI dependency: extract user from session cookie or Bearer token."""

import hashlib

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.auth.session import validate_session
from artiFACT.kernel.db import get_db
from artiFACT.kernel.exceptions import Unauthorized
from artiFACT.kernel.models import FcApiKey, FcUser


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session_id: str | None = Cookie(None, alias="session_id"),
    authorization: str | None = Header(None),
) -> FcUser:
    """Extract user from session cookie (Redis) or Bearer token (DB lookup)."""
    # Try session cookie first
    if session_id:
        user = await validate_session(session_id, db)
        if user:
            request.state.user = user
            return user

    # Try Bearer token
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        key_hash = hashlib.sha256(token.encode()).hexdigest()
        result = await db.execute(select(FcApiKey).where(FcApiKey.key_hash == key_hash))
        api_key = result.scalar_one_or_none()
        if api_key:
            if api_key.expires_at is not None:
                from datetime import datetime, timezone

                if api_key.expires_at < datetime.now(timezone.utc):
                    raise Unauthorized("API key expired")
            user_result = await db.execute(
                select(FcUser).where(FcUser.user_uid == api_key.user_uid)
            )
            user = user_result.scalar_one_or_none()
            if user and user.is_active:
                request.state.user = user
                return user

    raise Unauthorized("Authentication required")
