"""Add is_program flag to fc_node.

Revision ID: 001b94b328b9
Revises: fa4eefb85d7f
Create Date: 2026-04-03 01:06:39.126695
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001b94b328b9"
down_revision: Union[str, Sequence[str], None] = "fa4eefb85d7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_program boolean column and seed known programs."""
    op.add_column(
        "fc_node",
        sa.Column(
            "is_program",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    # Seed known program nodes
    op.execute(
        "UPDATE fc_node SET is_program = true "
        "WHERE title IN ('artiFACT', 'Boatwing H-12', 'SNIPE-B')"
    )


def downgrade() -> None:
    """Remove is_program column."""
    op.drop_column("fc_node", "is_program")
