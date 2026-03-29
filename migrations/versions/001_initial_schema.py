"""Initial schema: fc_user, fc_node, fc_node_permission, fc_system_config, fc_api_key, fc_user_ai_key.

Revision ID: 001
Revises:
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fc_user",
        sa.Column(
            "user_uid",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("cac_dn", sa.Text(), nullable=False),
        sa.Column("edipi", sa.String(10), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("global_role", sa.String(20), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("user_uid"),
        sa.UniqueConstraint("cac_dn"),
        sa.UniqueConstraint("edipi"),
        sa.CheckConstraint(
            "global_role IN ('admin','signatory','approver','subapprover','contributor','viewer')",
            name="ck_user_global_role",
        ),
    )
    op.create_index("idx_user_cac", "fc_user", ["cac_dn"])
    op.create_index("idx_user_edipi", "fc_user", ["edipi"])

    op.create_table(
        "fc_node",
        sa.Column(
            "node_uid",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("parent_node_uid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("node_depth", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by_uid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("node_uid"),
        sa.ForeignKeyConstraint(["parent_node_uid"], ["fc_node.node_uid"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_uid"], ["fc_user.user_uid"]),
    )
    op.create_index("idx_node_parent", "fc_node", ["parent_node_uid"])
    op.create_index("idx_node_slug", "fc_node", ["slug"])

    op.create_table(
        "fc_node_permission",
        sa.Column(
            "permission_uid",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("granted_by_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("permission_uid"),
        sa.ForeignKeyConstraint(["user_uid"], ["fc_user.user_uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_uid"], ["fc_node.node_uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_uid"], ["fc_user.user_uid"]),
        sa.UniqueConstraint("user_uid", "node_uid", "revoked_at", name="uq_perm_user_node_revoked"),
        sa.CheckConstraint(
            "role IN ('signatory','approver','subapprover','contributor','viewer')",
            name="ck_perm_role",
        ),
    )
    op.create_index(
        "idx_perm_user",
        "fc_node_permission",
        ["user_uid"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "idx_perm_node",
        "fc_node_permission",
        ["node_uid"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "fc_system_config",
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by_uid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("key"),
        sa.ForeignKeyConstraint(["updated_by_uid"], ["fc_user.user_uid"]),
    )

    op.create_table(
        "fc_api_key",
        sa.Column(
            "key_uid",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("scopes", postgresql.JSONB(), server_default=sa.text("'[\"read\"]'::jsonb")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("key_uid"),
        sa.ForeignKeyConstraint(["user_uid"], ["fc_user.user_uid"], ondelete="CASCADE"),
    )

    op.create_table(
        "fc_user_ai_key",
        sa.Column(
            "key_uid",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("encrypted_key", postgresql.BYTEA(), nullable=False),
        sa.Column("key_prefix", sa.String(10), nullable=True),
        sa.Column("model_override", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("key_uid"),
        sa.ForeignKeyConstraint(["user_uid"], ["fc_user.user_uid"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_uid", "provider", name="uq_ai_key_user_provider"),
        sa.CheckConstraint(
            "provider IN ('openai','anthropic','azure_openai','bedrock')",
            name="ck_ai_key_provider",
        ),
    )


def downgrade() -> None:
    op.drop_table("fc_user_ai_key")
    op.drop_table("fc_api_key")
    op.drop_table("fc_system_config")
    op.drop_table("fc_node_permission")
    op.drop_table("fc_node")
    op.drop_table("fc_user")
