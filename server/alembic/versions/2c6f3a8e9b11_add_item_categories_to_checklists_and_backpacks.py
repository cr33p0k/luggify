"""add item categories to checklists and backpacks

Revision ID: 2c6f3a8e9b11
Revises: e6f1c2a9b4d8
Create Date: 2026-04-20 18:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2c6f3a8e9b11"
down_revision = "e6f1c2a9b4d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "checklists",
        sa.Column("item_categories", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column(
        "user_backpacks",
        sa.Column("item_categories", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )


def downgrade() -> None:
    op.drop_column("user_backpacks", "item_categories")
    op.drop_column("checklists", "item_categories")
