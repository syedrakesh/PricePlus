"""Remove is_available column from discovered_products table

Revision ID: e7f8a9b0c1d2
Revises: d5e3f2a1b002
Create Date: 2026-09-10 22:42:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'd5e3f2a1b002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('discovered_products', 'is_available')


def downgrade() -> None:
    op.add_column('discovered_products', sa.Column('is_available', sa.Boolean(), nullable=False, server_default='true'))
