"""add baggage metadata to user backpacks

Revision ID: 9f1d7e5c4b21
Revises: c4f7e91b5a2d
Create Date: 2026-04-11 05:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9f1d7e5c4b21"
down_revision = "c4f7e91b5a2d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_backpacks",
        sa.Column("name", sa.String(), nullable=False, server_default="Рюкзак"),
    )
    op.add_column(
        "user_backpacks",
        sa.Column("kind", sa.String(), nullable=False, server_default="backpack"),
    )
    op.add_column(
        "user_backpacks",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_backpacks",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.execute("UPDATE user_backpacks SET name = 'Рюкзак' WHERE name IS NULL OR btrim(name) = ''")
    op.execute("UPDATE user_backpacks SET kind = 'backpack' WHERE kind IS NULL OR btrim(kind) = ''")
    op.execute("UPDATE user_backpacks SET sort_order = 0 WHERE sort_order IS NULL")
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (PARTITION BY checklist_id, user_id ORDER BY created_at, id) AS rn
            FROM user_backpacks
        )
        UPDATE user_backpacks ub
        SET is_default = CASE WHEN ranked.rn = 1 THEN TRUE ELSE FALSE END,
            sort_order = ranked.rn - 1
        FROM ranked
        WHERE ranked.id = ub.id
        """
    )


def downgrade() -> None:
    op.drop_column("user_backpacks", "is_default")
    op.drop_column("user_backpacks", "sort_order")
    op.drop_column("user_backpacks", "kind")
    op.drop_column("user_backpacks", "name")
