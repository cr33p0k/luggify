"""Add origin_city to checklists

Revision ID: b5e8f2a1c3d7
Revises: 419df1506e55
Create Date: 2026-02-24 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5e8f2a1c3d7'
down_revision: Union[str, Sequence[str], None] = '419df1506e55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('checklists', sa.Column('origin_city', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('checklists', 'origin_city')
