"""Add smart_tags and smart_tags_text to fc_fact_version

Revision ID: 356146896c1b
Revises: f236640d1e37
Create Date: 2026-04-02 04:41:26.680335

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '356146896c1b'
down_revision: Union[str, Sequence[str], None] = 'f236640d1e37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'fc_fact_version',
        sa.Column('smart_tags', postgresql.JSONB(astext_type=sa.Text()),
                  server_default=sa.text("'[]'::jsonb"), nullable=False),
    )
    op.add_column(
        'fc_fact_version',
        sa.Column('smart_tags_text', sa.Text(), server_default=sa.text("''"), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('fc_fact_version', 'smart_tags_text')
    op.drop_column('fc_fact_version', 'smart_tags')
