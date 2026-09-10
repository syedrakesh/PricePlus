"""Add compare_at_price, is_on_sale, is_discontinued to discovered_products

Revision ID: b3c9e1f4d002
Revises: 6e3478f1ce71
Create Date: 2026-09-10 20:22:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3c9e1f4d002'
down_revision: Union[str, None] = '6e3478f1ce71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'discovered_products',
        sa.Column(
            'compare_at_price',
            sa.Numeric(precision=12, scale=4),
            nullable=True,
            comment='Original price before sale (Shopify compare_at_price); None if not on sale',
        ),
    )
    op.add_column(
        'discovered_products',
        sa.Column(
            'is_on_sale',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
            comment='True when compare_at_price > current_price',
        ),
    )
    op.add_column(
        'discovered_products',
        sa.Column(
            'is_discontinued',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
            comment='True when product price is $0.00 (hidden/discontinued by seller)',
        ),
    )


def downgrade() -> None:
    op.drop_column('discovered_products', 'is_discontinued')
    op.drop_column('discovered_products', 'is_on_sale')
    op.drop_column('discovered_products', 'compare_at_price')
