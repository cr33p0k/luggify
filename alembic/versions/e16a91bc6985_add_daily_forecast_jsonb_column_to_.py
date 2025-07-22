from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# идентификаторы ревизии
revision = 'e16a91bc6985'
down_revision = 'fc422d2397a7'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('checklists', sa.Column('daily_forecast', postgresql.JSONB(), nullable=True))

def downgrade():
    op.drop_column('checklists', 'daily_forecast')

