"""Add fc_signature table.

Revision ID: 002
Revises: 001
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fc_signature",
        sa.Column(
            "signature_uid",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("node_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signed_by_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "signed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("fact_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("signature_uid"),
        sa.ForeignKeyConstraint(["node_uid"], ["fc_node.node_uid"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["signed_by_uid"], ["fc_user.user_uid"], ondelete="RESTRICT"),
    )
    op.create_index("idx_sig_node", "fc_signature", ["node_uid"])
    op.create_index("idx_sig_signer", "fc_signature", ["signed_by_uid"])


def downgrade() -> None:
    op.drop_index("idx_sig_signer", table_name="fc_signature")
    op.drop_index("idx_sig_node", table_name="fc_signature")
    op.drop_table("fc_signature")
