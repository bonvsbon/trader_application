"""add journal snapshot fields to closed trades

Revision ID: 0008_closed_trade_journal
Revises: 0007_analysis_providers
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_closed_trade_journal"
down_revision = "0007_analysis_providers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("closed_trades", sa.Column("entry_price", sa.Float(), nullable=True))
    op.add_column("closed_trades", sa.Column("exit_price", sa.Float(), nullable=True))
    op.add_column(
        "closed_trades",
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("closed_trades", sa.Column("exit_reason", sa.String(length=16), nullable=True))
    op.add_column("closed_trades", sa.Column("strategy_reason", sa.Text(), nullable=True))
    op.add_column("closed_trades", sa.Column("ai_reason", sa.Text(), nullable=True))
    op.add_column("closed_trades", sa.Column("decision", sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column("closed_trades", "decision")
    op.drop_column("closed_trades", "ai_reason")
    op.drop_column("closed_trades", "strategy_reason")
    op.drop_column("closed_trades", "exit_reason")
    op.drop_column("closed_trades", "open_time")
    op.drop_column("closed_trades", "exit_price")
    op.drop_column("closed_trades", "entry_price")
