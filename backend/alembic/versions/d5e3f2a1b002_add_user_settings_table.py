"""Add user_settings table for discovery rate and concurrency config

Revision ID: d5e3f2a1b002
Revises: c4d2a5b8e001
Create Date: 2026-09-10 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd5e3f2a1b002'
down_revision: Union[str, None] = 'c4d2a5b8e001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_settings',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('discovery_concurrency', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('discovery_min_delay', sa.Float(), nullable=False, server_default='0.8'),
        sa.Column('discovery_max_delay', sa.Float(), nullable=False, server_default='1.5'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_table('user_settings')
