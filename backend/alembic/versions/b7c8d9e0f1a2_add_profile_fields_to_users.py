"""Add full_name and phone_number columns to users table

Revision ID: b7c8d9e0f1a2
Revises: a8c7b6d5e4f3
Create Date: 2026-09-12 16:03:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = 'a8c7b6d5e4f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('full_name', sa.String(length=150), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column('phone_number', sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'phone_number')
    op.drop_column('users', 'full_name')
