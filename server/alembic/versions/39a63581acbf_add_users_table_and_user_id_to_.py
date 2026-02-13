"""add_users_table_and_user_id_to_checklists

Revision ID: 39a63581acbf
Revises: 517964269cb0
Create Date: 2026-02-13 16:48:14.385617

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39a63581acbf'
down_revision: Union[str, Sequence[str], None] = '517964269cb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создаём таблицу users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

    # Добавляем user_id в checklists (nullable для обратной совместимости)
    op.add_column('checklists', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index('ix_checklists_user_id', 'checklists', ['user_id'])
    op.create_foreign_key(
        'fk_checklists_user_id',
        'checklists', 'users',
        ['user_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_checklists_user_id', 'checklists', type_='foreignkey')
    op.drop_index('ix_checklists_user_id', 'checklists')
    op.drop_column('checklists', 'user_id')
    op.drop_index('ix_users_username', 'users')
    op.drop_index('ix_users_email', 'users')
    op.drop_index('ix_users_id', 'users')
    op.drop_table('users')
