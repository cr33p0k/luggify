"""add packed quantities to checklists and baggage

Revision ID: d1e4f7a8c2b3
Revises: b7c2e1a4d9f0
Create Date: 2026-04-11 21:15:00.000000
"""

import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d1e4f7a8c2b3"
down_revision = "b7c2e1a4d9f0"
branch_labels = None
depends_on = None


def _build_packed_map(checked_items, item_quantities):
    checked_items = checked_items or []
    item_quantities = item_quantities or {}
    packed = {}
    for item in checked_items:
        normalized_quantity = item_quantities.get(item) or item_quantities.get(str(item).strip().lower().replace("ё", "е")) or 1
        try:
            packed[item] = max(int(normalized_quantity), 1)
        except (TypeError, ValueError):
            packed[item] = 1
    return packed


def upgrade() -> None:
    op.add_column(
        "checklists",
        sa.Column("packed_quantities", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column(
        "user_backpacks",
        sa.Column("packed_quantities", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )

    bind = op.get_bind()

    checklist_rows = bind.execute(
        sa.text("SELECT id, checked_items, item_quantities FROM checklists")
    ).fetchall()
    for row in checklist_rows:
        packed_quantities = _build_packed_map(row.checked_items, row.item_quantities)
        bind.execute(
            sa.text("UPDATE checklists SET packed_quantities = CAST(:packed AS JSON) WHERE id = :id"),
            {"id": row.id, "packed": json.dumps(packed_quantities)},
        )

    backpack_rows = bind.execute(
        sa.text("SELECT id, checked_items, item_quantities FROM user_backpacks")
    ).fetchall()
    for row in backpack_rows:
        packed_quantities = _build_packed_map(row.checked_items, row.item_quantities)
        bind.execute(
            sa.text("UPDATE user_backpacks SET packed_quantities = CAST(:packed AS JSON) WHERE id = :id"),
            {"id": row.id, "packed": json.dumps(packed_quantities)},
        )


def downgrade() -> None:
    op.drop_column("user_backpacks", "packed_quantities")
    op.drop_column("checklists", "packed_quantities")
