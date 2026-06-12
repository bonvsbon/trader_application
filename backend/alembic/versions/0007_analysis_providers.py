"""add analysis provider registry

Revision ID: 0007_analysis_providers
Revises: 0006_closed_trade_review
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_analysis_providers"
down_revision = "0006_closed_trade_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_providers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("provider_type", sa.String(length=24), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("transport", sa.String(length=32), nullable=True),
        sa.Column("endpoint", sa.String(length=2048), nullable=True),
        sa.Column("secret_ref", sa.String(length=128), nullable=True),
        sa.Column("timeout_sec", sa.Float(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("allowed_tools", sa.JSON(), nullable=False),
        sa.Column("discovered_tools", sa.JSON(), nullable=False),
        sa.Column("health", sa.String(length=16), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("display_name"),
    )
    op.create_index(
        "ix_analysis_providers_display_name",
        "analysis_providers",
        ["display_name"],
        unique=True,
    )
    op.create_index(
        "ix_analysis_providers_provider_type",
        "analysis_providers",
        ["provider_type"],
    )
    op.create_index(
        "ix_analysis_providers_health",
        "analysis_providers",
        ["health"],
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_providers_health", table_name="analysis_providers")
    op.drop_index("ix_analysis_providers_provider_type", table_name="analysis_providers")
    op.drop_index("ix_analysis_providers_display_name", table_name="analysis_providers")
    op.drop_table("analysis_providers")
