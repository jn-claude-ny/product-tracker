"""Baseline schema — full current state of all models

Revision ID: 001
Revises:
Create Date: 2026-04-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('role', sa.String(50), nullable=False, server_default='user'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # ------------------------------------------------------------------
    # websites
    # ------------------------------------------------------------------
    op.create_table(
        'websites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('base_url', sa.String(512), nullable=False),
        sa.Column('allowed_domains', sa.JSON(), nullable=True),
        sa.Column('sitemap_url', sa.String(512), nullable=False),
        sa.Column('use_playwright', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('wait_selector', sa.String(255), nullable=True),
        sa.Column('scrape_delay_seconds', sa.Numeric(5, 2), nullable=False, server_default='3.0'),
        sa.Column('randomize_delay', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('proxy_group', sa.String(100), nullable=True),
        sa.Column('alert_cooldown_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('cron_schedule', sa.String(100), nullable=True),
        sa.Column('discord_webhook_url', sa.String(512), nullable=True),
        sa.Column('crawl_state', sa.String(20), nullable=False, server_default='never_crawled'),
        sa.Column('crawl_progress', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_products_expected', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('products_discovered', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('products_processed', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('last_crawl_completed_at', sa.DateTime(), nullable=True),
        sa.Column('sitemap_etag', sa.String(255), nullable=True),
        sa.Column('sitemap_last_checked', sa.DateTime(), nullable=True),
        sa.Column('is_crawling', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('current_task_id', sa.String(255), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_error_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_websites_user_id', 'websites', ['user_id'], unique=False)

    # ------------------------------------------------------------------
    # categories
    # ------------------------------------------------------------------
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('website_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('url_pattern', sa.String(512), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_categories_website_id', 'categories', ['website_id'], unique=False)

    # ------------------------------------------------------------------
    # selectors
    # ------------------------------------------------------------------
    op.create_table(
        'selectors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('website_id', sa.Integer(), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=False),
        sa.Column('selector_type', sa.String(20), nullable=False, server_default='css'),
        sa.Column('selector_value', sa.Text(), nullable=False),
        sa.Column('post_process', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_selectors_website_id', 'selectors', ['website_id'], unique=False)

    # ------------------------------------------------------------------
    # tracking_rules
    # ------------------------------------------------------------------
    op.create_table(
        'tracking_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('website_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('rule_type', sa.String(50), nullable=False),
        sa.Column('rule_value', sa.String(512), nullable=False),
        sa.Column('alert_on_new', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('alert_on_price_drop', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('alert_on_back_in_stock', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('price_threshold_type', sa.String(20), nullable=True),
        sa.Column('price_threshold_value', sa.Numeric(10, 2), nullable=True),
        sa.Column('min_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('max_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tracking_rules_website_id', 'tracking_rules', ['website_id'], unique=False)

    # ------------------------------------------------------------------
    # discord_webhooks
    # ------------------------------------------------------------------
    op.create_table(
        'discord_webhooks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('website_id', sa.Integer(), nullable=False),
        sa.Column('webhook_url', sa.String(512), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_discord_webhooks_website_id', 'discord_webhooks', ['website_id'], unique=False)

    # ------------------------------------------------------------------
    # products
    # ------------------------------------------------------------------
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('website_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(1024), nullable=False),
        sa.Column('sku', sa.String(255), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('brand', sa.String(255), nullable=True),
        sa.Column('image', sa.String(1024), nullable=True),
        sa.Column('categories', sa.JSON(), nullable=True),
        sa.Column('gender', sa.String(50), nullable=True),
        sa.Column('category', sa.String(255), nullable=True),
        sa.Column('color', sa.String(100), nullable=True),
        sa.Column('price_current', sa.Numeric(10, 2), nullable=True),
        sa.Column('price_previous', sa.Numeric(10, 2), nullable=True),
        sa.Column('currency', sa.String(10), nullable=True, server_default='USD'),
        sa.Column('is_new', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('is_on_sale', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('availability', sa.String(100), nullable=True),
        sa.Column('available', sa.Boolean(), nullable=True),
        sa.Column('inventory_level', sa.Integer(), nullable=True),
        sa.Column('first_seen', sa.DateTime(), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('last_price_change', sa.DateTime(), nullable=True),
        sa.Column('detail_last_fetched', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_products_website_id', 'products', ['website_id'], unique=False)
    op.create_index('idx_product_website_url', 'products', ['website_id', 'url'], unique=False)
    op.create_index('idx_product_gender', 'products', ['gender'], unique=False)
    op.create_index('idx_product_is_new', 'products', ['is_new'], unique=False)
    op.create_index('idx_product_is_on_sale', 'products', ['is_on_sale'], unique=False)

    # ------------------------------------------------------------------
    # product_snapshots
    # ------------------------------------------------------------------
    op.create_table(
        'product_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('price', sa.Numeric(10, 2), nullable=True),
        sa.Column('currency', sa.String(10), nullable=True),
        sa.Column('availability', sa.String(50), nullable=True),
        sa.Column('hash', sa.String(64), nullable=True),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_product_snapshots_product_id', 'product_snapshots', ['product_id'], unique=False)
    op.create_index('ix_product_snapshots_created_at', 'product_snapshots', ['created_at'], unique=False)
    op.create_index('ix_product_snapshots_hash', 'product_snapshots', ['hash'], unique=False)
    op.create_index('idx_snapshot_product_created', 'product_snapshots', ['product_id', 'created_at'], unique=False)

    # ------------------------------------------------------------------
    # product_variants
    # ------------------------------------------------------------------
    op.create_table(
        'product_variants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('variant_sku', sa.String(255), nullable=False),
        sa.Column('size', sa.String(50), nullable=True),
        sa.Column('color', sa.String(100), nullable=True),
        sa.Column('price', sa.Numeric(10, 2), nullable=True),
        sa.Column('stock_state', sa.String(100), nullable=True),
        sa.Column('available', sa.Boolean(), nullable=True),
        sa.Column('inventory_level', sa.Integer(), nullable=True),
        sa.Column('last_checked', sa.DateTime(), nullable=False),
        sa.Column('first_seen', sa.DateTime(), nullable=False),
        sa.Column('last_in_stock', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_variant_product', 'product_variants', ['product_id'], unique=False)
    op.create_index('idx_variant_product_sku', 'product_variants', ['product_id', 'variant_sku'], unique=False)

    # ------------------------------------------------------------------
    # alerts
    # ------------------------------------------------------------------
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.String(50), nullable=False),
        sa.Column('state_hash', sa.String(64), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_alerts_user_id', 'alerts', ['user_id'], unique=False)
    op.create_index('ix_alerts_product_id', 'alerts', ['product_id'], unique=False)
    op.create_index('idx_alert_product_type_hash', 'alerts', ['product_id', 'alert_type', 'state_hash'], unique=False)

    # ------------------------------------------------------------------
    # tracked_products
    # ------------------------------------------------------------------
    op.create_table(
        'tracked_products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('priority',
                  sa.Enum('now', 'urgent', 'high', 'moderate', 'normal', name='priority_enum'),
                  nullable=False, server_default='normal'),
        sa.Column('crawl_period_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('price_direction',
                  sa.Enum('above', 'below', name='price_direction_enum'),
                  nullable=True),
        sa.Column('price_reference', sa.Numeric(10, 2), nullable=True),
        sa.Column('price_condition',
                  sa.Enum('greater_than', 'less_than', 'equal_to', name='price_condition_enum'),
                  nullable=True),
        sa.Column('price_threshold', sa.Numeric(10, 2), nullable=True),
        sa.Column('discord_webhook_url', sa.String(512), nullable=True),
        sa.Column('size_filter', sa.JSON(), nullable=True),
        sa.Column('availability_filter', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tracked_products_user_id', 'tracked_products', ['user_id'], unique=False)

    # ------------------------------------------------------------------
    # discord_pending_users
    # ------------------------------------------------------------------
    op.create_table(
        'discord_pending_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('discord_id', sa.String(64), nullable=False),
        sa.Column('discord_name', sa.String(255), nullable=False),
        sa.Column('discord_avatar_url', sa.String(512), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('request_status',
                  sa.Enum('pending', 'approved', 'rejected', name='discord_request_status_enum'),
                  nullable=False, server_default='pending'),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('admin_message_id', sa.String(64), nullable=True),
        sa.Column('admin_channel_id', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_discord_pending_users_discord_id', 'discord_pending_users', ['discord_id'], unique=True)
    op.create_index('ix_discord_pending_users_request_status', 'discord_pending_users', ['request_status'], unique=False)

    # ------------------------------------------------------------------
    # user_discord_links
    # ------------------------------------------------------------------
    op.create_table(
        'user_discord_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('discord_id', sa.String(64), nullable=False),
        sa.Column('discord_name', sa.String(255), nullable=False),
        sa.Column('discord_avatar_url', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_user_discord_links_user_id'),
        sa.UniqueConstraint('discord_id', name='uq_user_discord_links_discord_id'),
    )
    op.create_index('ix_user_discord_links_user_id', 'user_discord_links', ['user_id'], unique=True)
    op.create_index('ix_user_discord_links_discord_id', 'user_discord_links', ['discord_id'], unique=True)

    # ------------------------------------------------------------------
    # discord_orders
    # ------------------------------------------------------------------
    op.create_table(
        'discord_orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('discord_user_id', sa.String(64), nullable=False),
        sa.Column('discord_channel_id', sa.String(64), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('alert_type',
                  sa.Enum('restock', 'price_drop', name='discord_alert_type_enum'),
                  nullable=False, server_default='restock'),
        sa.Column('size_filter', sa.String(100), nullable=True),
        sa.Column('status',
                  sa.Enum('active', 'cancelled', name='discord_order_status_enum'),
                  nullable=False, server_default='active'),
        sa.Column('last_alert_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_discord_orders_discord_user_id', 'discord_orders', ['discord_user_id'], unique=False)
    op.create_index('ix_discord_orders_user_id', 'discord_orders', ['user_id'], unique=False)
    op.create_index('ix_discord_orders_product_id', 'discord_orders', ['product_id'], unique=False)
    op.create_index('ix_discord_orders_status', 'discord_orders', ['status'], unique=False)


def downgrade() -> None:
    op.drop_table('discord_orders')
    op.drop_table('user_discord_links')
    op.drop_table('discord_pending_users')
    op.drop_table('tracked_products')
    op.drop_table('alerts')
    op.drop_table('product_variants')
    op.drop_table('product_snapshots')
    op.drop_table('products')
    op.drop_table('discord_webhooks')
    op.drop_table('tracking_rules')
    op.drop_table('selectors')
    op.drop_table('categories')
    op.drop_table('websites')
    op.drop_table('users')

    op.execute("DROP TYPE IF EXISTS discord_order_status_enum")
    op.execute("DROP TYPE IF EXISTS discord_alert_type_enum")
    op.execute("DROP TYPE IF EXISTS discord_request_status_enum")
    op.execute("DROP TYPE IF EXISTS price_condition_enum")
    op.execute("DROP TYPE IF EXISTS price_direction_enum")
    op.execute("DROP TYPE IF EXISTS priority_enum")
