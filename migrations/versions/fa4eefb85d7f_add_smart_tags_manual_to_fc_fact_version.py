"""Add smart_tags_manual to fc_fact_version

Revision ID: fa4eefb85d7f
Revises: 356146896c1b
Create Date: 2026-04-02 18:06:56.574239

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fa4eefb85d7f'
down_revision: Union[str, Sequence[str], None] = '356146896c1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'fc_fact_version',
        sa.Column('smart_tags_manual', postgresql.JSONB(astext_type=sa.Text()),
                  server_default=sa.text("'[]'::jsonb"), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('fc_fact_version', 'smart_tags_manual')
