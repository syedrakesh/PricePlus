"""Add tracking frequencies, priority VIP flags, and extend plans schema

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-10 23:00:00.000000

"""
from datetime import UTC, datetime
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update plans table
    op.add_column('plans', sa.Column('slug', sa.String(length=50), nullable=True))
    op.create_unique_constraint('uq_plans_slug', 'plans', ['slug'])
    op.add_column('plans', sa.Column('max_priority_products', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('plans', sa.Column('is_public', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('plans', sa.Column('features', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # 2. Update tracked_products table
    op.add_column('tracked_products', sa.Column('tracking_interval_minutes', sa.Integer(), nullable=True))
    op.add_column('tracked_products', sa.Column('is_priority', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('tracked_products', sa.Column('next_check_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_tracked_products_next_check_at', 'tracked_products', ['next_check_at'])

    # 3. Update user_settings table
    op.add_column('user_settings', sa.Column('default_tracking_interval_minutes', sa.Integer(), nullable=False, server_default='360'))
    op.add_column('user_settings', sa.Column('preferred_check_hour', sa.Integer(), nullable=False, server_default='8'))

    # 4. Seed default plans (Free, Pro, Enterprise)
    now = datetime.now(UTC)
    plans_table = sa.table(
        'plans',
        sa.column('id', postgresql.UUID(as_uuid=True)),
        sa.column('name', sa.String),
        sa.column('slug', sa.String),
        sa.column('max_stores', sa.Integer),
        sa.column('max_tracked_products', sa.Integer),
        sa.column('poll_interval_mins', sa.Integer),
        sa.column('max_priority_products', sa.Integer),
        sa.column('price_usd', sa.Numeric),
        sa.column('is_active', sa.Boolean),
        sa.column('is_public', sa.Boolean),
        sa.column('features', postgresql.JSONB),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )

    op.bulk_insert(
        plans_table,
        [
            {
                'id': uuid.uuid4(),
                'name': 'Free Plan',
                'slug': 'free',
                'max_stores': 1,
                'max_tracked_products': 10,
                'poll_interval_mins': 1440,  # 24 hours
                'max_priority_products': 0,
                'price_usd': 0.00,
                'is_active': True,
                'is_public': True,
                'features': {'instant_alerts': False, 'csv_export': False, 'vip_monitoring': False},
                'created_at': now,
            },
            {
                'id': uuid.uuid4(),
                'name': 'Pro Plan',
                'slug': 'pro',
                'max_stores': 5,
                'max_tracked_products': 250,
                'poll_interval_mins': 360,  # 6 hours
                'max_priority_products': 25,
                'price_usd': 29.00,
                'is_active': True,
                'is_public': True,
                'features': {'instant_alerts': True, 'csv_export': True, 'vip_monitoring': True},
                'created_at': now,
            },
            {
                'id': uuid.uuid4(),
                'name': 'Enterprise Plan',
                'slug': 'enterprise',
                'max_stores': 25,
                'max_tracked_products': 2500,
                'poll_interval_mins': 60,   # 1 hour
                'max_priority_products': 500,
                'price_usd': 99.00,
                'is_active': True,
                'is_public': True,
                'features': {'instant_alerts': True, 'csv_export': True, 'vip_monitoring': True, 'webhooks': True},
                'created_at': now,
            },
        ]
    )


def downgrade() -> None:
    op.drop_column('user_settings', 'preferred_check_hour')
    op.drop_column('user_settings', 'default_tracking_interval_minutes')

    op.drop_index('ix_tracked_products_next_check_at', table_name='tracked_products')
    op.drop_column('tracked_products', 'next_check_at')
    op.drop_column('tracked_products', 'is_priority')
    op.drop_column('tracked_products', 'tracking_interval_minutes')

    op.drop_column('plans', 'features')
    op.drop_column('plans', 'is_public')
    op.drop_column('plans', 'max_priority_products')
    op.drop_constraint('uq_plans_slug', 'plans', type_='unique')
    op.drop_column('plans', 'slug')
