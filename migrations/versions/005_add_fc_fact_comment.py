"""Add fc_fact_comment table for threaded comments on fact versions."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fc_fact_comment",
        sa.Column(
            "comment_uid",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "version_uid",
            UUID(as_uuid=True),
            sa.ForeignKey("fc_fact_version.version_uid"),
            nullable=False,
        ),
        sa.Column(
            "parent_comment_uid",
            UUID(as_uuid=True),
            sa.ForeignKey("fc_fact_comment.comment_uid"),
            nullable=True,
        ),
        sa.Column(
            "comment_type",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'comment'"),
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column(
            "created_by_uid",
            UUID(as_uuid=True),
            sa.ForeignKey("fc_user.user_uid"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolved_by_uid",
            UUID(as_uuid=True),
            sa.ForeignKey("fc_user.user_uid"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "comment_type IN ('comment','challenge','resolution')",
            name="ck_comment_type",
        ),
    )
    op.create_index("idx_comment_version", "fc_fact_comment", ["version_uid"])


def downgrade() -> None:
    op.drop_index("idx_comment_version", table_name="fc_fact_comment")
    op.drop_table("fc_fact_comment")
