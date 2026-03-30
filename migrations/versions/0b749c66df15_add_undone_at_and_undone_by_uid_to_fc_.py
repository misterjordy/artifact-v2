"""Add undone_at and undone_by_uid to fc_event_log

Revision ID: 0b749c66df15
Revises: 006
Create Date: 2026-03-30 20:28:52.679903

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b749c66df15'
down_revision: Union[str, Sequence[str], None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add undo tracking columns to fc_event_log."""
    op.add_column('fc_event_log', sa.Column('undone_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('fc_event_log', sa.Column('undone_by_uid', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_event_undone_by', 'fc_event_log', 'fc_user',
        ['undone_by_uid'], ['user_uid'],
    )


def downgrade() -> None:
    """Remove undo tracking columns from fc_event_log."""
    op.drop_constraint('fk_event_undone_by', 'fc_event_log', type_='foreignkey')
    op.drop_column('fc_event_log', 'undone_by_uid')
    op.drop_column('fc_event_log', 'undone_at')
