"""Add products_fetched to discovery_runs for live progress tracking

Revision ID: c4d2a5b8e001
Revises: b3c9e1f4d002
Create Date: 2026-09-10 21:09:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4d2a5b8e001'
down_revision: Union[str, None] = 'b3c9e1f4d002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'discovery_runs',
        sa.Column(
            'products_fetched',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('0'),
            comment='Count of product .json fetches completed (for ETA progress)',
        ),
    )


def downgrade() -> None:
    op.drop_column('discovery_runs', 'products_fetched')
