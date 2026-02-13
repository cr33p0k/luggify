"""add_tg_id_to_users

Revision ID: a1b2c3d4e5f6
Revises: 39a63581acbf
Create Date: 2026-02-13 18:08:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '39a63581acbf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем tg_id в users
    op.add_column('users', sa.Column('tg_id', sa.String(), nullable=True))
    op.create_index('ix_users_tg_id', 'users', ['tg_id'], unique=True)

    # Делаем email и hashed_password nullable (для Telegram-пользователей)
    op.alter_column('users', 'email', existing_type=sa.String(), nullable=True)
    op.alter_column('users', 'hashed_password', existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.alter_column('users', 'hashed_password', existing_type=sa.String(), nullable=False)
    op.alter_column('users', 'email', existing_type=sa.String(), nullable=False)
    op.drop_index('ix_users_tg_id', 'users')
    op.drop_column('users', 'tg_id')
