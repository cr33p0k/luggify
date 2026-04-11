"""add trip reviews

Revision ID: 8c6d4b2f9a11
Revises: 11d2f957fac7
Create Date: 2026-04-11 00:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c6d4b2f9a11'
down_revision: Union[str, Sequence[str], None] = '11d2f957fac7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'trip_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('checklist_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('photo', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['checklist_id'], ['checklists.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('checklist_id', 'user_id', name='uq_trip_reviews_checklist_user'),
    )
    op.create_index(op.f('ix_trip_reviews_id'), 'trip_reviews', ['id'], unique=False)
    op.create_index(op.f('ix_trip_reviews_checklist_id'), 'trip_reviews', ['checklist_id'], unique=False)
    op.create_index(op.f('ix_trip_reviews_user_id'), 'trip_reviews', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_trip_reviews_user_id'), table_name='trip_reviews')
    op.drop_index(op.f('ix_trip_reviews_checklist_id'), table_name='trip_reviews')
    op.drop_index(op.f('ix_trip_reviews_id'), table_name='trip_reviews')
    op.drop_table('trip_reviews')
