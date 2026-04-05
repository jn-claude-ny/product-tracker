"""initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    op.create_table('websites',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('base_url', sa.String(length=512), nullable=False),
    sa.Column('allowed_domains', sa.JSON(), nullable=True),
    sa.Column('sitemap_url', sa.String(length=512), nullable=False),
    sa.Column('use_playwright', sa.Boolean(), nullable=False),
    sa.Column('wait_selector', sa.String(length=255), nullable=True),
    sa.Column('scrape_delay_seconds', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('randomize_delay', sa.Boolean(), nullable=False),
    sa.Column('proxy_group', sa.String(length=100), nullable=True),
    sa.Column('alert_cooldown_minutes', sa.Integer(), nullable=False),
    sa.Column('cron_schedule', sa.String(length=100), nullable=True),
    sa.Column('sitemap_etag', sa.String(length=255), nullable=True),
    sa.Column('sitemap_last_checked', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_websites_user_id'), 'websites', ['user_id'], unique=False)

    op.create_table('categories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('website_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('url_pattern', sa.String(length=512), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_categories_website_id'), 'categories', ['website_id'], unique=False)

    op.create_table('selectors',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('website_id', sa.Integer(), nullable=False),
    sa.Column('field_name', sa.String(length=100), nullable=False),
    sa.Column('selector_type', sa.String(length=20), nullable=False),
    sa.Column('selector_value', sa.Text(), nullable=False),
    sa.Column('post_process', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_selectors_website_id'), 'selectors', ['website_id'], unique=False)

    op.create_table('tracking_rules',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('website_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('rule_type', sa.String(length=50), nullable=False),
    sa.Column('rule_value', sa.String(length=512), nullable=False),
    sa.Column('alert_on_new', sa.Boolean(), nullable=False),
    sa.Column('alert_on_price_drop', sa.Boolean(), nullable=False),
    sa.Column('alert_on_back_in_stock', sa.Boolean(), nullable=False),
    sa.Column('price_threshold_type', sa.String(length=20), nullable=True),
    sa.Column('price_threshold_value', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('min_price', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('max_price', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tracking_rules_website_id'), 'tracking_rules', ['website_id'], unique=False)

    op.create_table('discord_webhooks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('website_id', sa.Integer(), nullable=False),
    sa.Column('webhook_url', sa.String(length=512), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_discord_webhooks_website_id'), 'discord_webhooks', ['website_id'], unique=False)

    op.create_table('products',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('website_id', sa.Integer(), nullable=False),
    sa.Column('url', sa.String(length=1024), nullable=False),
    sa.Column('sku', sa.String(length=255), nullable=True),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('brand', sa.String(length=255), nullable=True),
    sa.Column('image', sa.String(length=1024), nullable=True),
    sa.Column('categories', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_products_website_id'), 'products', ['website_id'], unique=False)
    op.create_index('idx_product_website_url', 'products', ['website_id', 'url'], unique=False)

    op.create_table('product_snapshots',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('currency', sa.String(length=10), nullable=True),
    sa.Column('availability', sa.String(length=50), nullable=True),
    sa.Column('hash', sa.String(length=64), nullable=True),
    sa.Column('metadata', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_product_snapshots_product_id'), 'product_snapshots', ['product_id'], unique=False)
    op.create_index(op.f('ix_product_snapshots_created_at'), 'product_snapshots', ['created_at'], unique=False)
    op.create_index(op.f('ix_product_snapshots_hash'), 'product_snapshots', ['hash'], unique=False)
    op.create_index('idx_snapshot_product_created', 'product_snapshots', ['product_id', 'created_at'], unique=False)

    op.create_table('alerts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('alert_type', sa.String(length=50), nullable=False),
    sa.Column('state_hash', sa.String(length=64), nullable=False),
    sa.Column('sent_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_user_id'), 'alerts', ['user_id'], unique=False)
    op.create_index(op.f('ix_alerts_product_id'), 'alerts', ['product_id'], unique=False)
    op.create_index('idx_alert_product_type_hash', 'alerts', ['product_id', 'alert_type', 'state_hash'], unique=False)


def downgrade() -> None:
    op.drop_table('alerts')
    op.drop_table('product_snapshots')
    op.drop_table('products')
    op.drop_table('discord_webhooks')
    op.drop_table('tracking_rules')
    op.drop_table('selectors')
    op.drop_table('categories')
    op.drop_table('websites')
    op.drop_table('users')
