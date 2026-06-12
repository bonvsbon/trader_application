"""add strategy configuration and trade proposals

Revision ID: 0004_strategy_proposals
Revises: 0003_mt5_runtime_config
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_strategy_proposals"
down_revision = "0003_mt5_runtime_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("preset_name", sa.String(length=64), nullable=False),
        sa.Column("d40_value", sa.Float(), nullable=False),
        sa.Column("d20_value", sa.Float(), nullable=False),
        sa.Column("reward_risk_ratio", sa.Float(), nullable=False),
        sa.Column("risk_pct", sa.Float(), nullable=False),
        sa.Column("require_news_clear", sa.Boolean(), nullable=False),
        sa.Column("signal_definition_confirmed", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "trade_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("sl", sa.Float(), nullable=False),
        sa.Column("tp", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("risk_pct", sa.Float(), nullable=False),
        sa.Column("strategy_name", sa.String(length=64), nullable=False),
        sa.Column("strategy_reason", sa.Text(), nullable=False),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("risk_decision", sa.String(length=8), nullable=False),
        sa.Column("risk_reasons", sa.JSON(), nullable=False),
        sa.Column("risk_warnings", sa.JSON(), nullable=False),
        sa.Column("order_idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("order_idempotency_key"),
    )
    op.create_index("ix_trade_proposals_status", "trade_proposals", ["status"])
    op.create_index("ix_trade_proposals_symbol", "trade_proposals", ["symbol"])


def downgrade() -> None:
    op.drop_index("ix_trade_proposals_symbol", table_name="trade_proposals")
    op.drop_index("ix_trade_proposals_status", table_name="trade_proposals")
    op.drop_table("trade_proposals")
    op.drop_table("strategy_config")
