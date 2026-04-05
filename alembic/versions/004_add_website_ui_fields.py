"""Add discord_webhook_url and crawl_progress to websites

Revision ID: 004
Revises: 003
Create Date: 2026-03-31

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Add discord_webhook_url column
    op.add_column('websites', sa.Column('discord_webhook_url', sa.String(512), nullable=True))
    
    # Add crawl_progress column with default value of 0
    op.add_column('websites', sa.Column('crawl_progress', sa.Integer(), nullable=True, server_default='0'))


def downgrade():
    # Remove the columns
    op.drop_column('websites', 'crawl_progress')
    op.drop_column('websites', 'discord_webhook_url')
