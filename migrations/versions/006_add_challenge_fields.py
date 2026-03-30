"""Add challenge fields to fc_fact_comment: proposed_sentence, resolution_state, resolution_note."""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fc_fact_comment",
        sa.Column("proposed_sentence", sa.Text, nullable=True),
    )
    op.add_column(
        "fc_fact_comment",
        sa.Column("resolution_state", sa.String(20), nullable=True),
    )
    op.add_column(
        "fc_fact_comment",
        sa.Column("resolution_note", sa.Text, nullable=True),
    )
    op.create_check_constraint(
        "ck_resolution_state",
        "fc_fact_comment",
        "resolution_state IN ('approved', 'rejected')",
    )
    op.create_index(
        "idx_comment_challenge_pending",
        "fc_fact_comment",
        ["comment_type", "resolution_state"],
        postgresql_where=sa.text("comment_type = 'challenge' AND resolution_state IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_comment_challenge_pending", table_name="fc_fact_comment")
    op.drop_constraint("ck_resolution_state", "fc_fact_comment", type_="check")
    op.drop_column("fc_fact_comment", "resolution_note")
    op.drop_column("fc_fact_comment", "resolution_state")
    op.drop_column("fc_fact_comment", "proposed_sentence")
