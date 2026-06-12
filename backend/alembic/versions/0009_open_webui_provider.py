"""add Open WebUI provider configuration

Revision ID: 0009_open_webui_provider
Revises: 0008_closed_trade_journal
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_open_webui_provider"
down_revision = "0008_closed_trade_journal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analysis_providers",
        sa.Column("model_name", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "analysis_providers",
        sa.Column(
            "web_search_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "analysis_providers",
        sa.Column(
            "discovered_models",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("analysis_providers", "discovered_models")
    op.drop_column("analysis_providers", "web_search_enabled")
    op.drop_column("analysis_providers", "model_name")
