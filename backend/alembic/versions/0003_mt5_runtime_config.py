"""add persisted MT5 runtime configuration

Revision ID: 0003_mt5_runtime_config
Revises: 0002_order_dedupe_fingerprint
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_mt5_runtime_config"
down_revision = "0002_order_dedupe_fingerprint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mt5_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("bridge_type", sa.String(length=16), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("timeout_sec", sa.Float(), nullable=False),
        sa.Column("heartbeat_max_age_sec", sa.Float(), nullable=False),
        sa.Column("expected_login", sa.Integer(), nullable=True),
        sa.Column("expected_server", sa.String(length=128), nullable=True),
        sa.Column("expected_account_type", sa.String(length=8), nullable=False),
        sa.Column("updated_by", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("mt5_config")
