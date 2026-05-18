"""add trip profile to checklists

Revision ID: e6f1c2a9b4d8
Revises: f3c9b7a1d2e4
Create Date: 2026-04-15 20:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e6f1c2a9b4d8"
down_revision = "f3c9b7a1d2e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "checklists",
        sa.Column("trip_profile", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )


def downgrade() -> None:
    op.drop_column("checklists", "trip_profile")
