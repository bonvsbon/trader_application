"""add user sessions and MT5 account ownership

Revision ID: 0011_identity_foundation
Revises: 0010_analysis_market_data
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_identity_foundation"
down_revision = "0010_analysis_market_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mt5_login", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("failed_login_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_mt5_login", "users", ["mt5_login"], unique=True)
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "mt5_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("login", sa.BigInteger(), nullable=False),
        sa.Column("server", sa.String(length=128), nullable=False),
        sa.Column("server_normalized", sa.String(length=128), nullable=False),
        sa.Column("account_type", sa.String(length=8), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "login",
            "server_normalized",
            name="uq_mt5_accounts_login_server",
        ),
    )
    op.create_index(
        "ix_mt5_accounts_owner_user_id",
        "mt5_accounts",
        ["owner_user_id"],
    )
    op.create_index("ix_mt5_accounts_login", "mt5_accounts", ["login"])

    op.create_table(
        "user_sessions",
        sa.Column("token_hash", sa.String(length=64), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("csrf_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])

    op.add_column(
        "mt5_config",
        sa.Column("mt5_account_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_mt5_config_mt5_account_id",
        "mt5_config",
        "mt5_accounts",
        ["mt5_account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_mt5_config_mt5_account_id",
        "mt5_config",
        ["mt5_account_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_mt5_config_mt5_account_id", table_name="mt5_config")
    op.drop_constraint(
        "fk_mt5_config_mt5_account_id",
        "mt5_config",
        type_="foreignkey",
    )
    op.drop_column("mt5_config", "mt5_account_id")
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_mt5_accounts_login", table_name="mt5_accounts")
    op.drop_index("ix_mt5_accounts_owner_user_id", table_name="mt5_accounts")
    op.drop_table("mt5_accounts")
    op.drop_index("ix_users_status", table_name="users")
    op.drop_index("ix_users_mt5_login", table_name="users")
    op.drop_table("users")
