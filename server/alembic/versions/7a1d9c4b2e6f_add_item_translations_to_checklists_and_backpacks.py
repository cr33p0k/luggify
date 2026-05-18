"""add item translations to checklists and backpacks

Revision ID: 7a1d9c4b2e6f
Revises: 4b8f2d1c7a90
Create Date: 2026-04-22 18:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7a1d9c4b2e6f"
down_revision: Union[str, None] = "4b8f2d1c7a90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "checklists",
        sa.Column("item_translations", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column(
        "user_backpacks",
        sa.Column("item_translations", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )


def downgrade() -> None:
    op.drop_column("user_backpacks", "item_translations")
    op.drop_column("checklists", "item_translations")
