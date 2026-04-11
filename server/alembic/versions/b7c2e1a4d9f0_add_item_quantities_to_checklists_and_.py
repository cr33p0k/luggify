"""add item quantities to checklists and baggage

Revision ID: b7c2e1a4d9f0
Revises: 9f1d7e5c4b21
Create Date: 2026-04-11 19:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7c2e1a4d9f0"
down_revision = "9f1d7e5c4b21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "checklists",
        sa.Column("item_quantities", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column(
        "user_backpacks",
        sa.Column("item_quantities", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )

    op.execute("UPDATE checklists SET item_quantities = '{}'::json WHERE item_quantities IS NULL")
    op.execute("UPDATE user_backpacks SET item_quantities = '{}'::json WHERE item_quantities IS NULL")


def downgrade() -> None:
    op.drop_column("user_backpacks", "item_quantities")
    op.drop_column("checklists", "item_quantities")
