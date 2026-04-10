"""add email verification fields

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-28

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = '166f2de7b1ba'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('is_email_verified', sa.Boolean(), server_default='false', nullable=True))
    op.add_column('users', sa.Column('email_verification_code', sa.String(), nullable=True))
    op.add_column('users', sa.Column('code_expires_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'code_expires_at')
    op.drop_column('users', 'email_verification_code')
    op.drop_column('users', 'is_email_verified')
