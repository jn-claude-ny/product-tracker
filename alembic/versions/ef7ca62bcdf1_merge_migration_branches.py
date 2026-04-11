"""Merge migration branches

Revision ID: ef7ca62bcdf1
Revises: 003, 006
Create Date: 2026-04-12 00:16:20.344135

"""
from alembic import op
import sqlalchemy as sa


revision = 'ef7ca62bcdf1'
down_revision = ('003', '006')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
