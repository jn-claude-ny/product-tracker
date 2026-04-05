"""Add tracked_products table

Revision ID: 4b2c8e9f1a2b
Revises: 3ab6955b280d
Create Date: 2026-03-28 06:56:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '4b2c8e9f1a2b'
down_revision = '3ab6955b280d'
branch_labels = None
depends_on = None


def upgrade():
    # Create tracked_products table
    op.create_table('tracked_products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('priority', sa.Enum('urgent', 'moderate', 'normal', name='priority_enum'), nullable=False),
        sa.Column('crawl_period_hours', sa.Integer(), nullable=False),
        sa.Column('price_condition', sa.Enum('greater_than', 'less_than', 'equal_to', name='price_condition_enum'), nullable=True),
        sa.Column('price_threshold', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('discord_webhook_url', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tracked_products_user_id'), 'tracked_products', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_tracked_products_user_id'), table_name='tracked_products')
    op.drop_table('tracked_products')
    # Drop enums if they exist
    op.execute('DROP TYPE IF EXISTS priority_enum')
    op.execute('DROP TYPE IF EXISTS price_condition_enum')
