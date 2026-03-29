"""SQLAlchemy table definitions (single source of truth)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

metadata = MetaData()


class Base(DeclarativeBase):
    metadata = metadata


class FcUser(Base):
    __tablename__ = "fc_user"

    user_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cac_dn: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    edipi: Mapped[str | None] = mapped_column(String(10), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    global_role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="viewer",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "global_role IN ('admin','signatory','approver','subapprover','contributor','viewer')",
            name="ck_user_global_role",
        ),
        Index("idx_user_cac", "cac_dn"),
        Index("idx_user_edipi", "edipi"),
    )


class FcNode(Base):
    __tablename__ = "fc_node"

    node_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    parent_node_uid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_node.node_uid", ondelete="RESTRICT"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    node_depth: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by_uid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_user.user_uid"), nullable=True
    )

    __table_args__ = (
        Index("idx_node_parent", "parent_node_uid"),
        Index("idx_node_slug", "slug"),
    )


class FcNodePermission(Base):
    __tablename__ = "fc_node_permission"

    permission_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_user.user_uid", ondelete="CASCADE"), nullable=False
    )
    node_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_node.node_uid", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    granted_by_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_user.user_uid"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('signatory','approver','subapprover','contributor','viewer')",
            name="ck_perm_role",
        ),
        UniqueConstraint("user_uid", "node_uid", "revoked_at", name="uq_perm_user_node_revoked"),
        Index("idx_perm_user", "user_uid", postgresql_where="revoked_at IS NULL"),
        Index("idx_perm_node", "node_uid", postgresql_where="revoked_at IS NULL"),
    )


class FcSystemConfig(Base):
    __tablename__ = "fc_system_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by_uid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_user.user_uid"), nullable=True
    )


class FcApiKey(Base):
    __tablename__ = "fc_api_key"

    key_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_user.user_uid", ondelete="CASCADE"), nullable=False
    )
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    scopes: Mapped[dict] = mapped_column(JSONB, default=["read"])
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class FcUserAiKey(Base):
    __tablename__ = "fc_user_ai_key"

    key_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_user.user_uid", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    encrypted_key: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    key_prefix: Mapped[str | None] = mapped_column(String(10), nullable=True)
    model_override: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "provider IN ('openai','anthropic','azure_openai','bedrock')",
            name="ck_ai_key_provider",
        ),
        UniqueConstraint("user_uid", "provider", name="uq_ai_key_user_provider"),
    )
