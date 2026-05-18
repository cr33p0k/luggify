"""add child profile id to user backpacks

Revision ID: 4b8f2d1c7a90
Revises: 2c6f3a8e9b11
Create Date: 2026-04-20 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4b8f2d1c7a90"
down_revision: Union[str, None] = "2c6f3a8e9b11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_backpacks", sa.Column("child_profile_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_user_backpacks_child_profile_id"), "user_backpacks", ["child_profile_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_backpacks_child_profile_id"), table_name="user_backpacks")
    op.drop_column("user_backpacks", "child_profile_id")
