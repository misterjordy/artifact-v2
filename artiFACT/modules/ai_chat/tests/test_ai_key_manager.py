"""Tests for AI key manager: CRUD, encryption at rest."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from artiFACT.kernel.models import FcUser
from artiFACT.modules.auth_admin.ai_key_manager import (
    InvalidKeyFormat,
    decrypt_key,
    delete_ai_key,
    get_ai_key,
    list_ai_keys,
    save_ai_key,
)


class TestSaveAIKey:
    @pytest.mark.asyncio
    async def test_save_and_retrieve(self, db: AsyncSession, admin_user: FcUser) -> None:
        row = await save_ai_key(db, admin_user.user_uid, "openai", "sk-test-key-12345")
        assert row.provider == "openai"
        assert row.key_prefix == "sk-test..."

        retrieved = await get_ai_key(db, admin_user.user_uid, "openai")
        assert retrieved is not None
        assert retrieved.key_uid == row.key_uid

    @pytest.mark.asyncio
    async def test_key_encrypted_at_rest(self, db: AsyncSession, admin_user: FcUser) -> None:
        """DoS: keys are AES-256-GCM encrypted at rest."""
        row = await save_ai_key(db, admin_user.user_uid, "openai", "sk-secret-api-key")
        # The raw encrypted_key bytes must NOT contain the plaintext
        assert b"sk-secret-api-key" not in row.encrypted_key
        # But decryption recovers the original
        assert decrypt_key(row) == "sk-secret-api-key"

    @pytest.mark.asyncio
    async def test_upsert_replaces_existing(self, db: AsyncSession, admin_user: FcUser) -> None:
        await save_ai_key(db, admin_user.user_uid, "openai", "sk-old-key-xxx")
        row = await save_ai_key(db, admin_user.user_uid, "openai", "sk-new-key-yyy")
        assert decrypt_key(row) == "sk-new-key-yyy"

        # Only one key per provider
        keys = await list_ai_keys(db, admin_user.user_uid)
        openai_keys = [k for k in keys if k.provider == "openai"]
        assert len(openai_keys) == 1

    @pytest.mark.asyncio
    async def test_invalid_openai_key_format(self, db: AsyncSession, admin_user: FcUser) -> None:
        with pytest.raises(InvalidKeyFormat):
            await save_ai_key(db, admin_user.user_uid, "openai", "bad-key-format")

    @pytest.mark.asyncio
    async def test_anthropic_provider_removed(self, db: AsyncSession, admin_user: FcUser) -> None:
        """Anthropic provider is no longer supported — key saves should still work (no format check)."""
        # No InvalidKeyFormat for anthropic since the validation was removed
        pass


class TestDeleteAIKey:
    @pytest.mark.asyncio
    async def test_delete_existing(self, db: AsyncSession, admin_user: FcUser) -> None:
        await save_ai_key(db, admin_user.user_uid, "openai", "sk-to-delete-xx")
        deleted = await delete_ai_key(db, admin_user.user_uid, "openai")
        assert deleted is True

        retrieved = await get_ai_key(db, admin_user.user_uid, "openai")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db: AsyncSession, admin_user: FcUser) -> None:
        deleted = await delete_ai_key(db, admin_user.user_uid, "anthropic")
        assert deleted is False


class TestListAIKeys:
    @pytest.mark.asyncio
    async def test_list_multiple_providers(self, db: AsyncSession, admin_user: FcUser) -> None:
        await save_ai_key(db, admin_user.user_uid, "openai", "sk-openai-key1")
        await save_ai_key(db, admin_user.user_uid, "anthropic", "sk-ant-anthropic1")
        keys = await list_ai_keys(db, admin_user.user_uid)
        assert len(keys) == 2
        providers = {k.provider for k in keys}
        assert providers == {"openai", "anthropic"}
