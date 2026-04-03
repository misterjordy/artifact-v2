"""Add program_description to fc_node

Revision ID: 336aaaae7666
Revises: 001b94b328b9
Create Date: 2026-04-03 02:17:18.636325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '336aaaae7666'
down_revision: Union[str, Sequence[str], None] = '001b94b328b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('fc_node', sa.Column('program_description', sa.Text(), nullable=True))
    op.add_column('fc_node', sa.Column('program_description_source', sa.String(length=10), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('fc_node', 'program_description_source')
    op.drop_column('fc_node', 'program_description')
