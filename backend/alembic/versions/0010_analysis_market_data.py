"""add analysis runtime provenance and market data config

Revision ID: 0010_analysis_market_data
Revises: 0009_open_webui_provider
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_analysis_market_data"
down_revision = "0009_open_webui_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analysis_providers",
        sa.Column(
            "capability_tools",
            sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_table(
        "analysis_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("capability", sa.String(length=48), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=True),
        sa.Column("provider_type", sa.String(length=24), nullable=True),
        sa.Column("provider_name", sa.String(length=100), nullable=True),
        sa.Column("model_or_tool", sa.String(length=200), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("input_summary", sa.JSON(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_analysis_snapshots_correlation_id",
        "analysis_snapshots",
        ["correlation_id"],
    )
    op.create_index(
        "ix_analysis_snapshots_capability",
        "analysis_snapshots",
        ["capability"],
    )
    op.create_index(
        "ix_analysis_snapshots_success",
        "analysis_snapshots",
        ["success"],
    )
    op.create_table(
        "market_data_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("endpoint", sa.String(length=2048), nullable=False),
        sa.Column("feed", sa.String(length=24), nullable=False),
        sa.Column("api_key_ref", sa.String(length=128), nullable=True),
        sa.Column("api_secret_ref", sa.String(length=128), nullable=True),
        sa.Column("default_symbols", sa.JSON(), nullable=False),
        sa.Column("max_symbols", sa.Integer(), nullable=False),
        sa.Column("timeout_sec", sa.Float(), nullable=False),
        sa.Column("updated_by", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("market_data_config")
    op.drop_index("ix_analysis_snapshots_success", table_name="analysis_snapshots")
    op.drop_index("ix_analysis_snapshots_capability", table_name="analysis_snapshots")
    op.drop_index(
        "ix_analysis_snapshots_correlation_id",
        table_name="analysis_snapshots",
    )
    op.drop_table("analysis_snapshots")
    op.drop_column("analysis_providers", "capability_tools")
