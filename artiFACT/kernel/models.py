"""SQLAlchemy table definitions (single source of truth)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
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
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, TSVECTOR, UUID
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


class FcFact(Base):
    __tablename__ = "fc_fact"

    fact_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    node_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_node.node_uid", ondelete="RESTRICT"), nullable=False
    )
    current_published_version_uid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    current_signed_version_uid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    is_retired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by_uid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_user.user_uid"), nullable=True
    )
    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retired_by_uid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_user.user_uid"), nullable=True
    )

    __table_args__ = (
        Index("idx_fact_node", "node_uid", postgresql_where="NOT is_retired"),
        Index(
            "idx_fact_published",
            "current_published_version_uid",
            postgresql_where="current_published_version_uid IS NOT NULL",
        ),
    )


class FcFactVersion(Base):
    __tablename__ = "fc_fact_version"

    version_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fact_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_fact.fact_uid", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    display_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_tags: Mapped[list] = mapped_column(JSONB, default=list)
    source_reference: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    last_verified_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    classification: Mapped[str] = mapped_column(String(64), default="UNCLASSIFIED")
    applies_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    supersedes_version_uid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_fact_version.version_uid"), nullable=True
    )
    created_by_uid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_user.user_uid"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    search_vector = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', display_sentence)", persisted=True),
    )

    __table_args__ = (
        CheckConstraint(
            "state IN ('proposed','challenged','accepted','rejected',"
            "'published','signed','withdrawn','retired')",
            name="ck_version_state",
        ),
        Index("idx_version_fact", "fact_uid"),
        Index("idx_version_state", "state"),
        Index("idx_version_search", "search_vector", postgresql_using="gin"),
        Index("idx_version_created_by", "created_by_uid"),
    )


class FcEventLog(Base):
    __tablename__ = "fc_event_log"

    event_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    actor_uid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_user.user_uid"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reversible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reverse_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("idx_event_entity", "entity_uid", "entity_type"),
        Index("idx_event_type", "event_type", "entity_type"),
        Index("idx_event_actor", "actor_uid"),
        Index("idx_event_occurred", "occurred_at"),
    )


class FcUserPreference(Base):
    __tablename__ = "fc_user_preference"

    user_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_user.user_uid", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)


class FcSignature(Base):
    __tablename__ = "fc_signature"

    signature_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    node_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_node.node_uid", ondelete="RESTRICT"), nullable=False
    )
    signed_by_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_user.user_uid", ondelete="RESTRICT"), nullable=False
    )
    signed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    fact_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_sig_node", "node_uid"),
        Index("idx_sig_signer", "signed_by_uid"),
    )


class FcAiUsage(Base):
    __tablename__ = "fc_ai_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_uid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fc_user.user_uid"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[float] = mapped_column(Integer, nullable=False, default=0)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_ai_usage_user", "user_uid"),
    )
