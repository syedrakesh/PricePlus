"""Add tracking_min_delay and tracking_max_delay to user_settings

Revision ID: a8c7b6d5e4f3
Revises: f9b8c7d6e5f4
Create Date: 2026-09-11 15:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8c7b6d5e4f3'
down_revision: Union[str, None] = 'f9b8c7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop legacy tracking_request_delay if exists and add tracking_min_delay & tracking_max_delay
    op.drop_column('user_settings', 'tracking_request_delay')
    op.add_column(
        'user_settings',
        sa.Column('tracking_min_delay', sa.Float(), nullable=False, server_default='0.2'),
    )
    op.add_column(
        'user_settings',
        sa.Column('tracking_max_delay', sa.Float(), nullable=False, server_default='0.5'),
    )


def downgrade() -> None:
    op.drop_column('user_settings', 'tracking_max_delay')
    op.drop_column('user_settings', 'tracking_min_delay')
    op.add_column(
        'user_settings',
        sa.Column('tracking_request_delay', sa.Float(), nullable=False, server_default='0.2'),
    )
