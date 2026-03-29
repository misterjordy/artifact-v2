"""Add fc_import_session table.

Revision ID: 003
Revises: 002
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fc_import_session",
        sa.Column(
            "session_uid",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("program_node_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_filename", sa.String(500), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("source_s3_key", sa.String(500), nullable=True),
        sa.Column(
            "granularity",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'standard'"),
        ),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("staged_facts_s3", sa.String(500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by_uid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("session_uid"),
        sa.ForeignKeyConstraint(["program_node_uid"], ["fc_node.node_uid"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_uid"], ["fc_user.user_uid"]),
        sa.CheckConstraint(
            "granularity IN ('brief','standard','exhaustive')",
            name="ck_import_granularity",
        ),
        sa.CheckConstraint(
            "status IN ('pending','analyzing','staged','proposed','approved','rejected','failed')",
            name="ck_import_status",
        ),
    )
    op.create_index("idx_import_program", "fc_import_session", ["program_node_uid"])
    op.create_index("idx_import_hash", "fc_import_session", ["source_hash"])


def downgrade() -> None:
    op.drop_index("idx_import_hash", table_name="fc_import_session")
    op.drop_index("idx_import_program", table_name="fc_import_session")
    op.drop_table("fc_import_session")
