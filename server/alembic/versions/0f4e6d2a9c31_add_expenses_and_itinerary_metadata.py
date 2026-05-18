"""add expenses and itinerary metadata

Revision ID: 0f4e6d2a9c31
Revises: 7a1d9c4b2e6f
Create Date: 2026-05-05 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0f4e6d2a9c31"
down_revision: Union[str, Sequence[str], None] = "7a1d9c4b2e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("checklists", sa.Column("expense_budget_amount", sa.Float(), nullable=True))
    op.add_column(
        "checklists",
        sa.Column("expense_base_currency", sa.String(), nullable=False, server_default="RUB"),
    )
    op.add_column("itinerary_events", sa.Column("lat", sa.Float(), nullable=True))
    op.add_column("itinerary_events", sa.Column("lng", sa.Float(), nullable=True))
    op.add_column("itinerary_events", sa.Column("place_source", sa.String(), nullable=True))
    op.add_column("itinerary_events", sa.Column("duration_minutes", sa.Integer(), nullable=True))
    op.add_column("itinerary_events", sa.Column("travel_buffer_minutes", sa.Integer(), nullable=True))
    op.add_column("itinerary_events", sa.Column("event_type", sa.String(), nullable=True))
    op.add_column(
        "itinerary_events",
        sa.Column("meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.create_table(
        "trip_expenses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("checklist_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("expense_date", sa.Date(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False, server_default="other"),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="RUB"),
        sa.Column("amount_base", sa.Float(), nullable=False),
        sa.Column("base_currency", sa.String(), nullable=False, server_default="RUB"),
        sa.Column("fx_rate", sa.Float(), nullable=False, server_default="1"),
        sa.Column("fx_rate_date", sa.String(), nullable=True),
        sa.Column("fx_provider", sa.String(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["checklist_id"], ["checklists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trip_expenses_id"), "trip_expenses", ["id"], unique=False)
    op.create_index(op.f("ix_trip_expenses_checklist_id"), "trip_expenses", ["checklist_id"], unique=False)
    op.create_index(op.f("ix_trip_expenses_created_by_user_id"), "trip_expenses", ["created_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_trip_expenses_created_by_user_id"), table_name="trip_expenses")
    op.drop_index(op.f("ix_trip_expenses_checklist_id"), table_name="trip_expenses")
    op.drop_index(op.f("ix_trip_expenses_id"), table_name="trip_expenses")
    op.drop_table("trip_expenses")
    op.drop_column("itinerary_events", "meta")
    op.drop_column("itinerary_events", "event_type")
    op.drop_column("itinerary_events", "travel_buffer_minutes")
    op.drop_column("itinerary_events", "duration_minutes")
    op.drop_column("itinerary_events", "place_source")
    op.drop_column("itinerary_events", "lng")
    op.drop_column("itinerary_events", "lat")
    op.drop_column("checklists", "expense_base_currency")
    op.drop_column("checklists", "expense_budget_amount")
