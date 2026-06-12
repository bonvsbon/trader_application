"""add operator review fields to closed trades

Revision ID: 0006_closed_trade_review
Revises: 0005_trade_history
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_closed_trade_review"
down_revision = "0005_trade_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "closed_trades",
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("closed_trades", sa.Column("review_note", sa.Text(), nullable=True))
    op.add_column("closed_trades", sa.Column("reviewed_by", sa.String(length=64), nullable=True))
    op.add_column(
        "closed_trades",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("closed_trades", "reviewed_at")
    op.drop_column("closed_trades", "reviewed_by")
    op.drop_column("closed_trades", "review_note")
    op.drop_column("closed_trades", "reviewed")
