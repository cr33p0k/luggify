"""add city_attractions table

Revision ID: e3a9d2e4b1c7
Revises: ad825a73b150
Create Date: 2026-04-10 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'e3a9d2e4b1c7'
down_revision: Union[str, Sequence[str], None] = 'ad825a73b150'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if 'city_attractions' not in inspector.get_table_names():
        op.create_table(
            'city_attractions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('city_name', sa.String(), nullable=False),
            sa.Column('data', sa.JSON(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_city_attractions_id'), 'city_attractions', ['id'], unique=False)
        op.create_index(op.f('ix_city_attractions_city_name'), 'city_attractions', ['city_name'], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if 'city_attractions' in inspector.get_table_names():
        indexes = {
            index["name"]
            for index in inspector.get_indexes('city_attractions')
            if index.get("name")
        }
        if op.f('ix_city_attractions_city_name') in indexes:
            op.drop_index(op.f('ix_city_attractions_city_name'), table_name='city_attractions')
        if op.f('ix_city_attractions_id') in indexes:
            op.drop_index(op.f('ix_city_attractions_id'), table_name='city_attractions')
        op.drop_table('city_attractions')
