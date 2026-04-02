"""CRUD operations for per-user AI API keys (AES-256-GCM encrypted at rest)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.crypto import decrypt, encrypt
from artiFACT.kernel.exceptions import AppError
from artiFACT.kernel.models import FcUserAiKey


class InvalidKeyFormat(AppError):
    status_code = 422

    def __init__(self, detail: str = "Invalid key format") -> None:
        super().__init__(detail=detail, code="INVALID_KEY_FORMAT")


def _validate_key_format(provider: str, plaintext_key: str) -> None:
    if provider == "openai" and not plaintext_key.startswith("sk-"):
        raise InvalidKeyFormat("OpenAI keys must start with 'sk-'")


async def save_ai_key(
    db: AsyncSession,
    user_uid: uuid.UUID,
    provider: str,
    plaintext_key: str,
    model_override: str | None = None,
) -> FcUserAiKey:
    """Encrypt and upsert an AI API key for a user+provider pair."""
    _validate_key_format(provider, plaintext_key)

    encrypted = encrypt(plaintext_key)
    prefix = plaintext_key[:7] + "..."

    stmt = select(FcUserAiKey).where(
        FcUserAiKey.user_uid == user_uid,
        FcUserAiKey.provider == provider,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.encrypted_key = encrypted
        existing.key_prefix = prefix
        existing.model_override = model_override
        await db.flush()
        return existing

    key_row = FcUserAiKey(
        user_uid=user_uid,
        provider=provider,
        encrypted_key=encrypted,
        key_prefix=prefix,
        model_override=model_override,
    )
    db.add(key_row)
    await db.flush()
    return key_row


async def get_ai_key(
    db: AsyncSession,
    user_uid: uuid.UUID,
    provider: str | None = None,
) -> FcUserAiKey | None:
    """Load the user's AI key row (first matching provider or any)."""
    stmt = select(FcUserAiKey).where(FcUserAiKey.user_uid == user_uid)
    if provider:
        stmt = stmt.where(FcUserAiKey.provider == provider)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_ai_keys(
    db: AsyncSession,
    user_uid: uuid.UUID,
) -> list[FcUserAiKey]:
    """List all AI keys for a user (metadata only, key stays encrypted)."""
    stmt = select(FcUserAiKey).where(FcUserAiKey.user_uid == user_uid)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_ai_key(
    db: AsyncSession,
    user_uid: uuid.UUID,
    provider: str,
) -> bool:
    """Delete a user's AI key for a provider. Returns True if deleted."""
    stmt = select(FcUserAiKey).where(
        FcUserAiKey.user_uid == user_uid,
        FcUserAiKey.provider == provider,
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if not row:
        return False
    await db.delete(row)
    await db.flush()
    return True


def decrypt_key(row: FcUserAiKey) -> str:
    """Convenience: decrypt the encrypted_key blob to plaintext."""
    return decrypt(row.encrypted_key)
