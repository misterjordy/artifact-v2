"""Add fc_import_staged_fact and session extensions

Revision ID: 0677bc35f84d
Revises: 0b749c66df15
Create Date: 2026-03-31 01:31:47.576349

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0677bc35f84d'
down_revision: Union[str, Sequence[str], None] = '0b749c66df15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('fc_import_staged_fact',
    sa.Column('staged_fact_uid', sa.UUID(), nullable=False),
    sa.Column('session_uid', sa.UUID(), nullable=False),
    sa.Column('display_sentence', sa.Text(), nullable=False),
    sa.Column('suggested_node_uid', sa.UUID(), nullable=True),
    sa.Column('node_confidence', sa.Float(), nullable=True),
    sa.Column('node_alternatives', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('duplicate_of_uid', sa.UUID(), nullable=True),
    sa.Column('similarity_score', sa.Float(), nullable=True),
    sa.Column('conflict_with_uid', sa.UUID(), nullable=True),
    sa.Column('conflict_reason', sa.Text(), nullable=True),
    sa.Column('resolution', sa.String(length=20), nullable=True),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('original_sentence', sa.Text(), nullable=True),
    sa.Column('source_chunk_index', sa.Integer(), nullable=True),
    sa.Column('metadata_tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("resolution IS NULL OR resolution IN ('keep_new','keep_existing','keep_both','edited','deleted')", name='ck_staged_fact_resolution'),
    sa.CheckConstraint("status IN ('pending','accepted','rejected','duplicate','conflict','orphaned')", name='ck_staged_fact_status'),
    sa.ForeignKeyConstraint(['conflict_with_uid'], ['fc_fact_version.version_uid'], ),
    sa.ForeignKeyConstraint(['duplicate_of_uid'], ['fc_fact_version.version_uid'], ),
    sa.ForeignKeyConstraint(['session_uid'], ['fc_import_session.session_uid'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['suggested_node_uid'], ['fc_node.node_uid'], ),
    sa.PrimaryKeyConstraint('staged_fact_uid')
    )
    op.create_index('idx_staged_fact_session', 'fc_import_staged_fact', ['session_uid'], unique=False)

    op.add_column('fc_import_session', sa.Column('source_text', sa.Text(), nullable=True))
    op.add_column('fc_import_session', sa.Column('constraint_node_uids', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('fc_import_session', sa.Column('input_type', sa.String(length=10), server_default='document', nullable=False))

    # Update status check constraint to include 'discarded'
    op.drop_constraint('ck_import_status', 'fc_import_session')
    op.create_check_constraint(
        'ck_import_status', 'fc_import_session',
        "status IN ('pending','analyzing','staged','proposed','approved','rejected','failed','discarded')"
    )

    # Add input_type check constraint
    op.create_check_constraint(
        'ck_import_input_type', 'fc_import_session',
        "input_type IN ('document','text')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_import_input_type', 'fc_import_session')

    op.drop_constraint('ck_import_status', 'fc_import_session')
    op.create_check_constraint(
        'ck_import_status', 'fc_import_session',
        "status IN ('pending','analyzing','staged','proposed','approved','rejected','failed')"
    )

    op.drop_column('fc_import_session', 'input_type')
    op.drop_column('fc_import_session', 'constraint_node_uids')
    op.drop_column('fc_import_session', 'source_text')
    op.drop_index('idx_staged_fact_session', table_name='fc_import_staged_fact')
    op.drop_table('fc_import_staged_fact')
