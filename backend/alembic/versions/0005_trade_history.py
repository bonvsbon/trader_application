"""add closed-trade history and order planned-risk

Revision ID: 0005_trade_history
Revises: 0004_strategy_proposals
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_trade_history"
down_revision = "0004_strategy_proposals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("planned_risk_amount", sa.Float(), nullable=True),
    )
    op.create_table(
        "closed_trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("profit", sa.Float(), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("matched_order_id", sa.Integer(), nullable=True),
        sa.Column("planned_risk_amount", sa.Float(), nullable=True),
        sa.Column("r_multiple", sa.Float(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ticket"),
    )
    op.create_index("ix_closed_trades_ticket", "closed_trades", ["ticket"])
    op.create_index("ix_closed_trades_symbol", "closed_trades", ["symbol"])


def downgrade() -> None:
    op.drop_index("ix_closed_trades_symbol", table_name="closed_trades")
    op.drop_index("ix_closed_trades_ticket", table_name="closed_trades")
    op.drop_table("closed_trades")
    op.drop_column("orders", "planned_risk_amount")
