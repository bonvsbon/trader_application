"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("sl", sa.Float(), nullable=True),
        sa.Column("tp", sa.Float(), nullable=True),
        sa.Column("risk_pct", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("decision", sa.String(length=8), nullable=False),
        sa.Column("account_type", sa.String(length=8), nullable=False),
        sa.Column("trading_mode", sa.String(length=32), nullable=False),
        sa.Column("strategy_reason", sa.Text(), nullable=True),
        sa.Column("ai_reason", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.String(length=64), nullable=False),
        sa.Column("order_ticket", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_orders_idempotency_key", "orders", ["idempotency_key"], unique=True)
    op.create_index("ix_orders_symbol", "orders", ["symbol"])
    op.create_index("ix_orders_state", "orders", ["state"])

    op.create_table(
        "risk_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=8), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_risk_decisions_idempotency_key", "risk_decisions", ["idempotency_key"]
    )
    op.create_index("ix_risk_decisions_symbol", "risk_decisions", ["symbol"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("event", sa.String(length=48), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("account_type", sa.String(length=8), nullable=True),
        sa.Column("trading_mode", sa.String(length=32), nullable=True),
        sa.Column("decision", sa.String(length=8), nullable=True),
        sa.Column("strategy_reason", sa.Text(), nullable=True),
        sa.Column("ai_reason", sa.Text(), nullable=True),
        sa.Column("user_approval", sa.Boolean(), nullable=True),
        sa.Column("mt5_response", sa.JSON(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_idempotency_key", "audit_logs", ["idempotency_key"])
    op.create_index("ix_audit_logs_event", "audit_logs", ["event"])

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("open_price", sa.Float(), nullable=False),
        sa.Column("sl", sa.Float(), nullable=True),
        sa.Column("tp", sa.Float(), nullable=True),
        sa.Column("profit", sa.Float(), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_positions_ticket", "positions", ["ticket"])
    op.create_index("ix_positions_symbol", "positions", ["symbol"])

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("step", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )

    op.create_table(
        "logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("level", sa.String(length=12), nullable=False),
        sa.Column("source", sa.String(length=48), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_logs_level", "logs", ["level"])
    op.create_index("ix_logs_source", "logs", ["source"])


def downgrade() -> None:
    op.drop_index("ix_logs_source", table_name="logs")
    op.drop_index("ix_logs_level", table_name="logs")
    op.drop_table("logs")
    op.drop_table("workflow_runs")
    op.drop_index("ix_positions_symbol", table_name="positions")
    op.drop_index("ix_positions_ticket", table_name="positions")
    op.drop_table("positions")
    op.drop_index("ix_audit_logs_event", table_name="audit_logs")
    op.drop_index("ix_audit_logs_idempotency_key", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_risk_decisions_symbol", table_name="risk_decisions")
    op.drop_index("ix_risk_decisions_idempotency_key", table_name="risk_decisions")
    op.drop_table("risk_decisions")
    op.drop_index("ix_orders_state", table_name="orders")
    op.drop_index("ix_orders_symbol", table_name="orders")
    op.drop_index("ix_orders_idempotency_key", table_name="orders")
    op.drop_table("orders")
