"""Business logic for auth_admin (session + dev-mode login)."""

import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.config import settings
from artiFACT.kernel.exceptions import Forbidden, Unauthorized
from artiFACT.kernel.models import FcUser


def hash_password(password: str) -> str:
    """Simple SHA-256 hash for dev-mode passwords. Not for production (CAC-only)."""
    return hashlib.sha256(password.encode()).hexdigest()


async def authenticate_dev(db: AsyncSession, username: str, password: str) -> FcUser:
    """Dev-mode authentication: check username (cac_dn) + password hash."""
    if settings.APP_ENV not in ("development", "test"):
        raise Forbidden("Password login disabled in production")

    result = await db.execute(select(FcUser).where(FcUser.cac_dn == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise Unauthorized("Invalid credentials")

    if user.password_hash != hash_password(password):
        raise Unauthorized("Invalid credentials")

    if not user.is_active:
        raise Unauthorized("Account deactivated")

    return user
