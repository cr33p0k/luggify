"""add user packing profile and baggage editors

Revision ID: f3c9b7a1d2e4
Revises: d1e4f7a8c2b3
Create Date: 2026-04-11 22:40:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "f3c9b7a1d2e4"
down_revision = "d1e4f7a8c2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("packing_profile", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column(
        "user_backpacks",
        sa.Column("editor_user_ids", postgresql.ARRAY(sa.Integer()), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("user_backpacks", "editor_user_ids")
    op.drop_column("users", "packing_profile")
