"""add rbac roles and permissions

Revision ID: e2e2f33dbf91
Revises: f8a9b0c1d2e3
Create Date: 2026-09-11 00:09:47.108708

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e2e2f33dbf91'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create permissions table
    op.create_table(
        'permissions',
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint('code', name=op.f('pk_permissions'))
    )

    # Create roles table
    op.create_table(
        'roles',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_roles'))
    )
    op.create_index(op.f('ix_roles_slug'), 'roles', ['slug'], unique=True)

    # Create role_permissions table
    op.create_table(
        'role_permissions',
        sa.Column('role_id', sa.Uuid(), nullable=False),
        sa.Column('permission_code', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['permission_code'], ['permissions.code'], name=op.f('fk_role_permissions_permission_code_permissions'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_role_permissions_role_id_roles'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('role_id', 'permission_code', name=op.f('pk_role_permissions'))
    )

    # Add columns to users table
    op.add_column('users', sa.Column('role_id', sa.Uuid(), nullable=True))
    op.add_column('users', sa.Column('custom_permissions', sa.JSON(), nullable=False, server_default='[]'))
    op.create_foreign_key(op.f('fk_users_role_id_roles'), 'users', 'roles', ['role_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint(op.f('fk_users_role_id_roles'), 'users', type_='foreignkey')
    op.drop_column('users', 'custom_permissions')
    op.drop_column('users', 'role_id')
    op.drop_table('role_permissions')
    op.drop_index(op.f('ix_roles_slug'), table_name='roles')
    op.drop_table('roles')
    op.drop_table('permissions')
