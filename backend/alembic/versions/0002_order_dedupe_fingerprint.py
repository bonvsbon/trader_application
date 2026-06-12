"""add atomic order dedupe fingerprint

Revision ID: 0002_order_dedupe_fingerprint
Revises: 0001_initial
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_order_dedupe_fingerprint"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("dedupe_fingerprint", sa.String(length=128), nullable=True))
    op.create_index(
        "ix_orders_dedupe_fingerprint",
        "orders",
        ["dedupe_fingerprint"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_orders_dedupe_fingerprint", table_name="orders")
    op.drop_column("orders", "dedupe_fingerprint")
