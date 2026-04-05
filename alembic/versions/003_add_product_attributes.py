"""Add product attributes for multi-site tracking

Revision ID: 003
Revises: 002
Create Date: 2026-03-31 01:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to products table
    op.add_column('products', sa.Column('gender', sa.String(20), nullable=True))
    op.add_column('products', sa.Column('color', sa.String(100), nullable=True))
    op.add_column('products', sa.Column('size_range', sa.String(100), nullable=True))
    op.add_column('products', sa.Column('price_current', sa.Numeric(10, 2), nullable=True))
    op.add_column('products', sa.Column('sale_price', sa.Numeric(10, 2), nullable=True))
    op.add_column('products', sa.Column('is_new', sa.Boolean, nullable=True, server_default='false'))
    op.add_column('products', sa.Column('is_on_sale', sa.Boolean, nullable=True, server_default='false'))
    op.add_column('products', sa.Column('availability', sa.String(50), nullable=True))
    op.add_column('products', sa.Column('variants_data', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    
    # Create product_variants table
    op.create_table(
        'product_variants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('sku', sa.String(255), nullable=True),
        sa.Column('size', sa.String(50), nullable=True),
        sa.Column('color', sa.String(100), nullable=True),
        sa.Column('price', sa.Numeric(10, 2), nullable=True),
        sa.Column('availability', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE')
    )
    
    # Add indexes
    op.create_index('idx_product_gender', 'products', ['gender'])
    op.create_index('idx_product_is_new', 'products', ['is_new'])
    op.create_index('idx_product_is_on_sale', 'products', ['is_on_sale'])
    op.create_index('idx_product_availability', 'products', ['availability'])
    op.create_index('idx_variant_product', 'product_variants', ['product_id'])
    op.create_index('idx_variant_sku', 'product_variants', ['sku'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_variant_sku', 'product_variants')
    op.drop_index('idx_variant_product', 'product_variants')
    op.drop_index('idx_product_availability', 'products')
    op.drop_index('idx_product_is_on_sale', 'products')
    op.drop_index('idx_product_is_new', 'products')
    op.drop_index('idx_product_gender', 'products')
    
    # Drop table
    op.drop_table('product_variants')
    
    # Drop columns
    op.drop_column('products', 'variants_data')
    op.drop_column('products', 'availability')
    op.drop_column('products', 'is_on_sale')
    op.drop_column('products', 'is_new')
    op.drop_column('products', 'sale_price')
    op.drop_column('products', 'price_current')
    op.drop_column('products', 'size_range')
    op.drop_column('products', 'color')
    op.drop_column('products', 'gender')
