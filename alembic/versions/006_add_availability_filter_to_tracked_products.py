"""Add availability_filter to tracked_products

Revision ID: 006
Revises: 005
Create Date: 2026-04-07

"""
from alembic import op
import sqlalchemy as sa


revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tracked_products', sa.Column('availability_filter', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('tracked_products', 'availability_filter')
