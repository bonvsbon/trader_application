"""scope trading persistence to an MT5 account

Revision ID: 0012_account_scoped_trading
Revises: 0011_identity_foundation
Create Date: 2026-06-13
"""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0012_account_scoped_trading"
down_revision = "0011_identity_foundation"
branch_labels = None
depends_on = None

SCOPED_TABLES = (
    "orders",
    "risk_decisions",
    "audit_logs",
    "positions",
    "closed_trades",
    "workflow_runs",
    "strategy_config",
    "analysis_snapshots",
    "trade_proposals",
)


def _default_account_id() -> int:
    bind = op.get_bind()
    account_id = bind.execute(sa.text("SELECT MIN(id) FROM mt5_accounts")).scalar()
    if account_id is not None:
        return int(account_id)

    now = datetime.now(timezone.utc)
    bind.execute(
        sa.text(
            """
            INSERT INTO users (
                mt5_login, display_name, password_hash, status, is_admin,
                failed_login_count, created_at, updated_at
            ) VALUES (
                -1, 'Legacy local owner', 'disabled', 'DISABLED', false,
                0, :now, :now
            )
            """
        ),
        {"now": now},
    )
    user_id = bind.execute(
        sa.text("SELECT id FROM users WHERE mt5_login = -1")
    ).scalar_one()
    bind.execute(
        sa.text(
            """
            INSERT INTO mt5_accounts (
                owner_user_id, login, server, server_normalized, account_type,
                display_name, enabled, created_at, updated_at
            ) VALUES (
                :user_id, -1, 'legacy-local', 'legacy-local', 'UNKNOWN',
                'Legacy local account', true, :now, :now
            )
            """
        ),
        {"user_id": user_id, "now": now},
    )
    return int(
        bind.execute(
            sa.text(
                "SELECT id FROM mt5_accounts "
                "WHERE login = -1 AND server_normalized = 'legacy-local'"
            )
        ).scalar_one()
    )


def _drop_unique_for_columns(table: str, columns: set[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    constraints = inspector.get_unique_constraints(table)
    naming_convention = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
    with op.batch_alter_table(
        table, naming_convention=naming_convention
    ) as batch:
        for constraint in constraints:
            if set(constraint.get("column_names") or []) == columns:
                name = constraint["name"] or (
                    f"uq_{table}_{constraint['column_names'][0]}"
                )
                batch.drop_constraint(name, type_="unique")


def upgrade() -> None:
    account_id = _default_account_id()

    for table in SCOPED_TABLES:
        op.add_column(
            table,
            sa.Column("mt5_account_id", sa.Integer(), nullable=True),
        )
        op.execute(
            sa.text(
                f"UPDATE {table} SET mt5_account_id = :account_id "
                "WHERE mt5_account_id IS NULL"
            ).bindparams(account_id=account_id)
        )
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                "mt5_account_id", existing_type=sa.Integer(), nullable=False
            )
            batch.create_foreign_key(
                f"fk_{table}_mt5_account_id",
                "mt5_accounts",
                ["mt5_account_id"],
                ["id"],
                ondelete="CASCADE",
            )
            batch.create_index(
                f"ix_{table}_mt5_account_id", ["mt5_account_id"]
            )

    with op.batch_alter_table("orders") as batch:
        batch.drop_index("ix_orders_idempotency_key")
        batch.drop_index("ix_orders_dedupe_fingerprint")
        batch.create_index("ix_orders_idempotency_key", ["idempotency_key"])
        batch.create_index(
            "ix_orders_dedupe_fingerprint", ["dedupe_fingerprint"]
        )
        batch.create_unique_constraint(
            "uq_orders_account_idempotency",
            ["mt5_account_id", "idempotency_key"],
        )
        batch.create_unique_constraint(
            "uq_orders_account_dedupe",
            ["mt5_account_id", "dedupe_fingerprint"],
        )

    _drop_unique_for_columns("closed_trades", {"ticket"})
    with op.batch_alter_table("closed_trades") as batch:
        batch.create_unique_constraint(
            "uq_closed_trades_account_ticket",
            ["mt5_account_id", "ticket"],
        )
    with op.batch_alter_table("positions") as batch:
        batch.create_unique_constraint(
            "uq_positions_account_ticket",
            ["mt5_account_id", "ticket"],
        )
    _drop_unique_for_columns("trade_proposals", {"order_idempotency_key"})
    with op.batch_alter_table("trade_proposals") as batch:
        batch.create_unique_constraint(
            "uq_trade_proposals_account_order_key",
            ["mt5_account_id", "order_idempotency_key"],
        )
    with op.batch_alter_table("strategy_config") as batch:
        batch.create_unique_constraint(
            "uq_strategy_config_account", ["mt5_account_id"]
        )

    # The pre-identity singleton config belongs to the same account as its data.
    op.execute(
        sa.text(
            "UPDATE mt5_config SET mt5_account_id = :account_id "
            "WHERE mt5_account_id IS NULL"
        ).bindparams(account_id=account_id)
    )
    with op.batch_alter_table("mt5_config") as batch:
        batch.drop_constraint(
            "fk_mt5_config_mt5_account_id", type_="foreignkey"
        )
        batch.alter_column(
            "mt5_account_id", existing_type=sa.Integer(), nullable=False
        )
        batch.create_foreign_key(
            "fk_mt5_config_mt5_account_id",
            "mt5_accounts",
            ["mt5_account_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("mt5_config") as batch:
        batch.drop_constraint(
            "fk_mt5_config_mt5_account_id", type_="foreignkey"
        )
        batch.alter_column(
            "mt5_account_id", existing_type=sa.Integer(), nullable=True
        )
        batch.create_foreign_key(
            "fk_mt5_config_mt5_account_id",
            "mt5_accounts",
            ["mt5_account_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("strategy_config") as batch:
        batch.drop_constraint(
            "uq_strategy_config_account", type_="unique"
        )
    with op.batch_alter_table("trade_proposals") as batch:
        batch.drop_constraint(
            "uq_trade_proposals_account_order_key", type_="unique"
        )
        batch.create_unique_constraint(
            "uq_trade_proposals_order_idempotency_key",
            ["order_idempotency_key"],
        )
    with op.batch_alter_table("positions") as batch:
        batch.drop_constraint(
            "uq_positions_account_ticket", type_="unique"
        )
    with op.batch_alter_table("closed_trades") as batch:
        batch.drop_constraint(
            "uq_closed_trades_account_ticket", type_="unique"
        )
        batch.create_unique_constraint(
            "uq_closed_trades_ticket", ["ticket"]
        )
    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint("uq_orders_account_dedupe", type_="unique")
        batch.drop_constraint(
            "uq_orders_account_idempotency", type_="unique"
        )
        batch.drop_index("ix_orders_dedupe_fingerprint")
        batch.drop_index("ix_orders_idempotency_key")
        batch.create_index(
            "ix_orders_dedupe_fingerprint",
            ["dedupe_fingerprint"],
            unique=True,
        )
        batch.create_index(
            "ix_orders_idempotency_key",
            ["idempotency_key"],
            unique=True,
        )

    for table in reversed(SCOPED_TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_mt5_account_id")
            batch.drop_constraint(
                f"fk_{table}_mt5_account_id", type_="foreignkey"
            )
            batch.drop_column("mt5_account_id")
