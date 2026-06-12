"""Pure domain models.

These use pydantic for validation/serialization but deliberately depend on
nothing from FastAPI, SQLAlchemy, or the bridge — they are the shared language
between the API edge, the Risk Engine, the bridge adapters, and persistence.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import (
    AccountType,
    BridgeHealth,
    OrderSide,
    OrderState,
    RiskDecision,
    TradingMode,
)


class OrderRequest(BaseModel):
    """A request to place an order — from a human (manual) or a strategy (auto).

    `idempotency_key` is mandatory: it is how the chokepoint deduplicates retries
    and prevents accidental double orders.
    """

    symbol: str
    side: OrderSide
    volume: float = Field(gt=0, description="Lot size")
    sl: float | None = None
    tp: float | None = None
    risk_pct: float | None = Field(default=None, gt=0)
    idempotency_key: str = Field(min_length=8)
    source: str = "manual"  # "manual" | "auto"
    strategy_reason: str | None = None
    ai_reason: str | None = None
    requested_by: str = "system"


class AccountInfo(BaseModel):
    account_type: AccountType
    login: int | None = None
    server: str | None = None
    currency: str = "USD"
    balance: float = 0.0
    equity: float = 0.0
    margin: float = 0.0
    free_margin: float = 0.0
    leverage: int = 0

    @property
    def free_margin_pct(self) -> float:
        if self.equity <= 0:
            return 0.0
        return (self.free_margin / self.equity) * 100.0


class Mt5RuntimeConfig(BaseModel):
    """Runtime bridge endpoint and the only MT5 account allowed to trade."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    bridge_type: str = "mock"
    host: str = "127.0.0.1"
    port: int = Field(default=5555, ge=1, le=65535)
    timeout_sec: float = Field(default=5.0, gt=0, le=60)
    heartbeat_max_age_sec: float = Field(default=15.0, gt=0, le=300)
    expected_login: int | None = Field(default=None, gt=0)
    expected_server: str | None = Field(default=None, max_length=128)
    expected_account_type: AccountType = AccountType.UNKNOWN

    @field_validator("bridge_type")
    @classmethod
    def validate_bridge_type(cls, value: str) -> str:
        if value not in {"mock", "ea_socket"}:
            raise ValueError("bridge_type must be mock or ea_socket")
        return value

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        value = value.strip()
        if not value or any(char.isspace() for char in value):
            raise ValueError("host must be a non-empty hostname or IP address")
        return value

    @field_validator("expected_server")
    @classmethod
    def normalize_server(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    def account_problems(self, account: AccountInfo) -> list[str]:
        if not self.enabled:
            return ["MT5 configuration is disabled"]
        problems: list[str] = []
        if self.bridge_type == "ea_socket":
            if self.expected_login is None:
                problems.append("Expected MT5 login is not configured")
            if self.expected_server is None:
                problems.append("Expected MT5 server is not configured")
            if self.expected_account_type is AccountType.UNKNOWN:
                problems.append("Expected MT5 account type is not configured")
        if self.expected_login is not None and account.login != self.expected_login:
            problems.append(
                f"Connected MT5 login {account.login or 'unknown'} does not match configured login"
            )
        if (
            self.expected_server is not None
            and (account.server or "").casefold() != self.expected_server.casefold()
        ):
            problems.append("Connected MT5 server does not match configured server")
        if (
            self.expected_account_type is not AccountType.UNKNOWN
            and account.account_type is not self.expected_account_type
        ):
            problems.append(
                "Connected MT5 account type does not match configured account type"
            )
        return problems


class StrategyPresetConfig(BaseModel):
    """Editable XAUUSD preset values; signal semantics remain explicitly gated."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    symbol: str = Field(default="XAUUSD", min_length=1, max_length=32)
    preset_name: str = Field(default="XAUUSD_D40_D20", min_length=1, max_length=64)
    d40_value: float = Field(default=40.0, gt=0)
    d20_value: float = Field(default=20.0, gt=0)
    reward_risk_ratio: float = Field(default=2.0, gt=0, le=10)
    risk_pct: float = Field(default=1.0, gt=0, le=100)
    require_news_clear: bool = True
    signal_definition_confirmed: bool = False

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class SymbolQuote(BaseModel):
    symbol: str
    bid: float
    ask: float
    spread_points: float
    time: datetime


class Candle(BaseModel):
    """One OHLC bar. `time` is the bar's open time (UTC)."""

    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class SymbolInfo(BaseModel):
    """Broker contract data required for position sizing."""

    symbol: str
    tick_size: float = Field(gt=0)
    tick_value: float = Field(gt=0)
    volume_min: float = Field(gt=0)
    volume_max: float = Field(gt=0)
    volume_step: float = Field(gt=0)


class Position(BaseModel):
    ticket: int
    symbol: str
    side: OrderSide
    volume: float
    open_price: float
    sl: float | None = None
    tp: float | None = None
    profit: float = 0.0
    open_time: datetime | None = None


class ClosedTrade(BaseModel):
    ticket: int
    symbol: str
    profit: float
    close_time: datetime
    # Journal context, when the bridge can supply it (all optional so the
    # today-only path and existing callers keep working).
    side: OrderSide | None = None
    volume: float | None = None
    entry_price: float | None = None
    exit_price: float | None = None
    open_time: datetime | None = None
    exit_reason: str | None = None  # e.g. "tp", "sl", "manual", "other"


class BridgeHealthStatus(BaseModel):
    health: BridgeHealth
    last_heartbeat: datetime | None = None
    detail: str = ""

    @property
    def is_healthy(self) -> bool:
        return self.health is BridgeHealth.HEALTHY


class NewsRisk(BaseModel):
    """Snapshot of news risk for a symbol.

    Phase 1 supplies an empty/neutral value (no real provider yet). Phase 2 fills
    it from the news provider. The Risk Engine treats `has_high_impact_within_window`
    as a hard BLOCK condition.
    """

    has_high_impact_within_window: bool = False
    minutes_to_next_high_impact: float | None = None
    score: float = 0.0
    summary: str = ""
    provider: str = "unavailable"
    is_live: bool = False


class VolatilityRisk(BaseModel):
    """Snapshot from a volatility/session provider."""

    abnormal: bool = False
    score: float = 0.0
    summary: str = ""
    provider: str = "unavailable"
    is_live: bool = False


class RiskContext(BaseModel):
    """Everything the Risk Engine needs to make a decision — gathered by the caller."""

    request: OrderRequest
    trading_mode: TradingMode
    account: AccountInfo
    bridge_health: BridgeHealth
    quote: SymbolQuote | None = None
    symbol_info: SymbolInfo | None = None
    positions: list[Position] = Field(default_factory=list)
    closed_trades_today: list[ClosedTrade] = Field(default_factory=list)
    open_positions: int = 0
    trades_today: int = 0
    daily_loss_pct: float = 0.0
    minutes_since_last_loss: float | None = None
    abnormal_volatility: bool = False
    volatility: VolatilityRisk = Field(default_factory=VolatilityRisk)
    news: NewsRisk = Field(default_factory=NewsRisk)
    config_problems: list[str] = Field(default_factory=list)
    data_problems: list[str] = Field(default_factory=list)
    estimated_loss: float | None = None
    estimated_reward: float | None = None
    sized_risk_pct: float | None = None
    max_volume_for_risk: float | None = None
    current_portfolio_risk_pct: float | None = None


class RiskResult(BaseModel):
    decision: RiskDecision
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.decision is RiskDecision.ALLOW

    @property
    def blocked(self) -> bool:
        return self.decision is RiskDecision.BLOCK


class OrderResult(BaseModel):
    """The outcome returned by the order chokepoint for every order attempt."""

    idempotency_key: str
    state: OrderState
    decision: RiskDecision
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    order_id: int | None = None
    mt5_response: dict | None = None
    account_type: AccountType = AccountType.UNKNOWN
    trading_mode: TradingMode = TradingMode.MANUAL_ONLY
    created_at: datetime | None = None
    message: str = ""
