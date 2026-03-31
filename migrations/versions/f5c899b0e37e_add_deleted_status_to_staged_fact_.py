"""Add deleted status to staged fact constraint

Revision ID: f5c899b0e37e
Revises: 0677bc35f84d
Create Date: 2026-03-31 02:29:27.383191

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f5c899b0e37e'
down_revision: Union[str, Sequence[str], None] = '0677bc35f84d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'deleted' to the staged fact status check constraint."""
    op.drop_constraint('ck_staged_fact_status', 'fc_import_staged_fact')
    op.create_check_constraint(
        'ck_staged_fact_status', 'fc_import_staged_fact',
        "status IN ('pending','accepted','rejected','duplicate','conflict','orphaned','deleted')"
    )


def downgrade() -> None:
    """Remove 'deleted' from the staged fact status check constraint."""
    op.drop_constraint('ck_staged_fact_status', 'fc_import_staged_fact')
    op.create_check_constraint(
        'ck_staged_fact_status', 'fc_import_staged_fact',
        "status IN ('pending','accepted','rejected','duplicate','conflict','orphaned')"
    )
