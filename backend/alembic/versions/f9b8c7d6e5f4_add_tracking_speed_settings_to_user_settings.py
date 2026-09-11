"""Add tracking_concurrency and tracking_request_delay columns to user_settings

Revision ID: f9b8c7d6e5f4
Revises: e2e2f33dbf91
Create Date: 2026-09-11 10:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9b8c7d6e5f4'
down_revision: Union[str, None] = 'e2e2f33dbf91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_settings',
        sa.Column('tracking_concurrency', sa.Integer(), nullable=False, server_default='5'),
    )
    op.add_column(
        'user_settings',
        sa.Column('tracking_request_delay', sa.Float(), nullable=False, server_default='0.2'),
    )


def downgrade() -> None:
    op.drop_column('user_settings', 'tracking_request_delay')
    op.drop_column('user_settings', 'tracking_concurrency')
