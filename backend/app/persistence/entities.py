"""SQLAlchemy ORM entities.

Every order, risk decision, and audit event is persisted. The `audit_logs` table
is the durable record required by the safety rules (strategy/AI/risk/approval/
MT5 response/timestamp/account/mode).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    """Application identity whose username is the user's MT5 login number."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mt5_login: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Mt5AccountRow(Base):
    """MT5 identity owned by an application user; no broker password is stored."""

    __tablename__ = "mt5_accounts"
    __table_args__ = (
        UniqueConstraint(
            "login",
            "server_normalized",
            name="uq_mt5_accounts_login_server",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    login: Mapped[int] = mapped_column(BigInteger, index=True)
    server: Mapped[str] = mapped_column(String(128))
    server_normalized: Mapped[str] = mapped_column(String(128))
    account_type: Mapped[str] = mapped_column(String(8))
    display_name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class UserSessionRow(Base):
    """Opaque browser session. Only hashes of session and CSRF tokens persist."""

    __tablename__ = "user_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OrderRow(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint(
            "mt5_account_id", "idempotency_key",
            name="uq_orders_account_idempotency",
        ),
        UniqueConstraint(
            "mt5_account_id", "dedupe_fingerprint",
            name="uq_orders_account_dedupe",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mt5_account_id: Mapped[int] = mapped_column(
        ForeignKey("mt5_accounts.id", ondelete="CASCADE"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    dedupe_fingerprint: Mapped[str | None] = mapped_column(
        String(128), index=True, nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    volume: Mapped[float] = mapped_column(Float)
    sl: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")
    state: Mapped[str] = mapped_column(String(24), index=True)
    decision: Mapped[str] = mapped_column(String(8))
    account_type: Mapped[str] = mapped_column(String(8))
    trading_mode: Mapped[str] = mapped_column(String(32))
    strategy_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[str] = mapped_column(String(64), default="system")
    order_ticket: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Planned risk amount at entry (account currency), used to compute the
    # realized R-multiple once the trade closes. None when sizing data was absent.
    planned_risk_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class RiskDecisionRow(Base):
    __tablename__ = "risk_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mt5_account_id: Mapped[int] = mapped_column(
        ForeignKey("mt5_accounts.id", ondelete="CASCADE"), index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    decision: Mapped[str] = mapped_column(String(8))
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLogRow(Base):
    """Durable, append-only audit trail for every order attempt."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mt5_account_id: Mapped[int] = mapped_column(
        ForeignKey("mt5_accounts.id", ondelete="CASCADE"), index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    event: Mapped[str] = mapped_column(String(48), index=True)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    account_type: Mapped[str | None] = mapped_column(String(8), nullable=True)
    trading_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(8), nullable=True)
    strategy_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_approval: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    mt5_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PositionRow(Base):
    """Snapshot of an open position synced from MT5."""

    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint(
            "mt5_account_id", "ticket", name="uq_positions_account_ticket"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mt5_account_id: Mapped[int] = mapped_column(
        ForeignKey("mt5_accounts.id", ondelete="CASCADE"), index=True
    )
    ticket: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    volume: Mapped[float] = mapped_column(Float)
    open_price: Mapped[float] = mapped_column(Float)
    sl: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit: Mapped[float] = mapped_column(Float, default=0.0)
    open_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ClosedTradeRow(Base):
    """A closed MT5 trade, synced from the bridge.

    Deduplicated by `ticket`. When the trade can be matched back to one of our
    orders (by `order_ticket`), the planned risk is copied and the realized
    R-multiple (`profit / planned_risk_amount`) is computed.
    """

    __tablename__ = "closed_trades"
    __table_args__ = (
        UniqueConstraint(
            "mt5_account_id", "ticket", name="uq_closed_trades_account_ticket"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mt5_account_id: Mapped[int] = mapped_column(
        ForeignKey("mt5_accounts.id", ondelete="CASCADE"), index=True
    )
    ticket: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str | None] = mapped_column(String(8), nullable=True)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit: Mapped[float] = mapped_column(Float, default=0.0)
    close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    matched_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planned_risk_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Journal snapshot: trade execution detail + the rationale captured at entry.
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    open_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)
    strategy_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Operator post-trade review (a trade journal, especially for losses).
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowRunRow(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mt5_account_id: Mapped[int] = mapped_column(
        ForeignKey("mt5_accounts.id", ondelete="CASCADE"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    step: Mapped[str] = mapped_column(String(48), default="")
    status: Mapped[str] = mapped_column(String(24), default="running")
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class LogRow(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(12), index=True)
    source: Mapped[str] = mapped_column(String(48), index=True)
    message: Mapped[str] = mapped_column(Text)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Mt5ConfigRow(Base):
    """Runtime MT5 bridge/account allowlist configuration for one account."""

    __tablename__ = "mt5_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mt5_account_id: Mapped[int] = mapped_column(
        ForeignKey("mt5_accounts.id", ondelete="CASCADE"),
        unique=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    bridge_type: Mapped[str] = mapped_column(String(16), default="mock")
    host: Mapped[str] = mapped_column(String(255), default="127.0.0.1")
    port: Mapped[int] = mapped_column(Integer, default=5555)
    timeout_sec: Mapped[float] = mapped_column(Float, default=5.0)
    heartbeat_max_age_sec: Mapped[float] = mapped_column(Float, default=15.0)
    expected_login: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_server: Mapped[str | None] = mapped_column(String(128), nullable=True)
    expected_account_type: Mapped[str] = mapped_column(String(8), default="UNKNOWN")
    updated_by: Mapped[str] = mapped_column(String(64), default="system")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class StrategyConfigRow(Base):
    __tablename__ = "strategy_config"
    __table_args__ = (
        UniqueConstraint("mt5_account_id", name="uq_strategy_config_account"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mt5_account_id: Mapped[int] = mapped_column(
        ForeignKey("mt5_accounts.id", ondelete="CASCADE"), index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    symbol: Mapped[str] = mapped_column(String(32), default="XAUUSD")
    preset_name: Mapped[str] = mapped_column(String(64), default="XAUUSD_D40_D20")
    d40_value: Mapped[float] = mapped_column(Float, default=40.0)
    d20_value: Mapped[float] = mapped_column(Float, default=20.0)
    reward_risk_ratio: Mapped[float] = mapped_column(Float, default=2.0)
    risk_pct: Mapped[float] = mapped_column(Float, default=1.0)
    require_news_clear: Mapped[bool] = mapped_column(Boolean, default=True)
    signal_definition_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[str] = mapped_column(String(64), default="system")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AnalysisProviderRow(Base):
    """Persisted non-secret configuration for AI and MCP analysis providers."""

    __tablename__ = "analysis_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    provider_type: Mapped[str] = mapped_column(String(24), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    transport: Mapped[str | None] = mapped_column(String(32), nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    web_search_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    secret_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timeout_sec: Mapped[float] = mapped_column(Float, default=10.0)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    allowed_tools: Mapped[list] = mapped_column(JSON, default=list)
    capability_tools: Mapped[dict] = mapped_column(JSON, default=dict)
    discovered_tools: Mapped[list] = mapped_column(JSON, default=list)
    discovered_models: Mapped[list] = mapped_column(JSON, default=list)
    health: Mapped[str] = mapped_column(String(16), default="UNKNOWN", index=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AnalysisSnapshotRow(Base):
    """Sanitized provenance for every runtime analysis provider attempt."""

    __tablename__ = "analysis_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mt5_account_id: Mapped[int] = mapped_column(
        ForeignKey("mt5_accounts.id", ondelete="CASCADE"), index=True
    )
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    capability: Mapped[str] = mapped_column(String(48), index=True)
    provider_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_or_tool: Mapped[str | None] = mapped_column(String(200), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MarketDataConfigRow(Base):
    """Singleton non-secret configuration for read-only realtime quotes."""

    __tablename__ = "market_data_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    provider: Mapped[str] = mapped_column(String(24), default="mt5")
    endpoint: Mapped[str] = mapped_column(
        String(2048), default="wss://stream.data.alpaca.markets/v2"
    )
    feed: Mapped[str] = mapped_column(String(24), default="iex")
    api_key_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    api_secret_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    default_symbols: Mapped[list] = mapped_column(JSON, default=list)
    max_symbols: Mapped[int] = mapped_column(Integer, default=25)
    timeout_sec: Mapped[float] = mapped_column(Float, default=10.0)
    updated_by: Mapped[str] = mapped_column(String(64), default="system")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class TradeProposalRow(Base):
    __tablename__ = "trade_proposals"
    __table_args__ = (
        UniqueConstraint(
            "mt5_account_id", "order_idempotency_key",
            name="uq_trade_proposals_account_order_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mt5_account_id: Mapped[int] = mapped_column(
        ForeignKey("mt5_accounts.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    entry_price: Mapped[float] = mapped_column(Float)
    sl: Mapped[float] = mapped_column(Float)
    tp: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
    risk_pct: Mapped[float] = mapped_column(Float)
    strategy_name: Mapped[str] = mapped_column(String(64))
    strategy_reason: Mapped[str] = mapped_column(Text)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_decision: Mapped[str] = mapped_column(String(8))
    risk_reasons: Mapped[list] = mapped_column(JSON, default=list)
    risk_warnings: Mapped[list] = mapped_column(JSON, default=list)
    order_idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
