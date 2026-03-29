"""Add fc_document_template table and seq column to fc_event_log."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "004"
down_revision = "9c6cc21350e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fc_document_template",
        sa.Column(
            "template_uid",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("abbreviation", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sections", JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_by_uid", UUID(as_uuid=True), sa.ForeignKey("fc_user.user_uid"), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.add_column(
        "fc_event_log",
        sa.Column("seq", sa.Integer, sa.Identity(always=True), nullable=False),
    )
    op.create_index("idx_event_seq", "fc_event_log", ["seq"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_event_seq", table_name="fc_event_log")
    op.drop_column("fc_event_log", "seq")
    op.drop_table("fc_document_template")
