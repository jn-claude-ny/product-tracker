"""Add availability, available, inventory_level to products and variants

Revision ID: 005
Revises: 003
Create Date: 2026-04-07

"""
from alembic import op
import sqlalchemy as sa


revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Products table — availability already added in 003, but only in DB not in model
    # Add available (bool) and inventory_level (int)
    op.add_column('products', sa.Column('available', sa.Boolean(), nullable=True))
    op.add_column('products', sa.Column('inventory_level', sa.Integer(), nullable=True))

    # product_variants table — add price, available, inventory_level
    # Note: migration 003 created product_variants with column 'sku' but the model uses 'variant_sku'
    # and columns 'availability' instead of 'stock_state'. The model was updated post-003 via direct DB changes.
    # We only add the truly new columns here.
    op.add_column('product_variants', sa.Column('price', sa.Numeric(10, 2), nullable=True))
    op.add_column('product_variants', sa.Column('available', sa.Boolean(), nullable=True))
    op.add_column('product_variants', sa.Column('inventory_level', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('product_variants', 'inventory_level')
    op.drop_column('product_variants', 'available')
    op.drop_column('product_variants', 'price')
    op.drop_column('products', 'inventory_level')
    op.drop_column('products', 'available')
