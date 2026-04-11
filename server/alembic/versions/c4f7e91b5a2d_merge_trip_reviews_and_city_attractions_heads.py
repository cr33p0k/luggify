"""merge trip reviews and city attractions heads

Revision ID: c4f7e91b5a2d
Revises: 8c6d4b2f9a11, e3a9d2e4b1c7
Create Date: 2026-04-11 01:22:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c4f7e91b5a2d"
down_revision: Union[str, Sequence[str], None] = ("8c6d4b2f9a11", "e3a9d2e4b1c7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
