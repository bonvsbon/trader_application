"""Application configuration — single source of truth, env-driven.

No risk value, lot size, account type, or trading mode is hardcoded anywhere in
the codebase; everything funnels through `Settings`. The Risk Engine and the
order chokepoint call `Settings.validate_safety()` and treat any problem as
"config missing" => BLOCK.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import AccountType, TradingMode

# Project root is four levels up: core -> app -> backend -> <root>.
_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Prefer the repo-root .env, fall back to a backend-local .env.
        env_file=(str(_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────────────────────
    app_env: str = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    api_auth_required: bool = False
    api_auth_token: str = ""
    api_operator_name: str = "operator"
    user_auth_enabled: bool = False
    auth_bootstrap_enabled: bool = True
    auth_cookie_name: str = "thangrod_session"
    auth_csrf_cookie_name: str = "thangrod_csrf"
    auth_session_hours: int = 12
    auth_max_failed_attempts: int = 5
    auth_lock_minutes: int = 15

    # ── Database ───────────────────────────────────────────────────────────
    database_url: str = ""

    # ── Trading mode ─────────────────────────────────────────────────────────
    trading_mode: TradingMode = TradingMode.MANUAL_ONLY

    # ── Safety flags ─────────────────────────────────────────────────────────
    allow_real_trading: bool = False
    allow_auto_real_full: bool = False
    emergency_stop: bool = False

    # ── MT5 bridge ───────────────────────────────────────────────────────────
    mt5_bridge_type: str = "mock"
    mt5_ea_host: str = "127.0.0.1"
    mt5_ea_port: int = 5555
    mt5_ea_shared_secret: str = ""
    mt5_ea_allow_remote_bind: bool = False
    mt5_bridge_timeout_sec: float = 5.0
    mt5_heartbeat_max_age_sec: float = 15.0
    mt5_expected_login: int | None = None
    mt5_expected_server: str = ""
    mt5_expected_account_type: AccountType = AccountType.UNKNOWN
    mock_bridge_health: str = "healthy"
    mock_account_type: AccountType = AccountType.DEMO

    # ── Bridge resilience (retry + circuit breaker) ──────────────────────────
    # Applied to idempotent bridge reads only; execute_order is never retried.
    bridge_retry_max_attempts: int = 2
    bridge_retry_backoff_base_sec: float = 0.2
    bridge_retry_backoff_max_sec: float = 2.0
    bridge_circuit_fail_threshold: int = 5
    bridge_circuit_reset_sec: float = 30.0

    # ── Risk configuration ───────────────────────────────────────────────────
    risk_max_risk_per_trade_pct: float = 1.0
    risk_max_portfolio_risk_pct: float = 5.0
    risk_daily_max_loss_pct: float = 3.0
    risk_max_trades_per_day: int = 5
    risk_max_open_positions: int = 3
    risk_max_spread_points: float = 50.0
    risk_cooldown_minutes_after_loss: int = 30
    risk_news_block_window_min: int = 30
    risk_min_free_margin_pct: float = 50.0
    risk_max_order_volume_lots: float = 1.0

    # ── Workflow ─────────────────────────────────────────────────────────────
    workflow_interval_seconds: int = 300
    workflow_auto_demo_enabled: bool = False
    # After consecutive failed cycles the scheduler backs off exponentially up to
    # this ceiling, then returns to the normal interval on the next success.
    workflow_max_backoff_seconds: int = 3600
    approval_expiry_minutes: int = 30
    reconciliation_expiry_minutes: int = 15
    reconciliation_batch_size: int = 20

    # ── Strategy / proposals ─────────────────────────────────────────────────
    strategy_xauusd_enabled: bool = False
    strategy_d40_value: float = 40.0
    strategy_d20_value: float = 20.0
    strategy_reward_risk_ratio: float = 2.0
    strategy_risk_pct: float = 1.0
    strategy_signal_definition_confirmed: bool = False
    strategy_timeframe: str = "H1"  # candle timeframe for the D40/D20 Donchian signal
    proposal_expiry_minutes: int = 15

    # ── AI providers (Phase 2 placeholders) ──────────────────────────────────
    ai_primary_provider: str = "claude"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    local_llm_url: str = ""

    # Analysis provider registry / MCP client
    mcp_allowed_hosts: str = "localhost,127.0.0.1,::1"
    mcp_max_discovered_tools: int = 100
    analysis_provider_allowed_hosts: str = "localhost,127.0.0.1,::1"
    openai_provider_allowed_hosts: str = "api.openai.com"
    analysis_provider_max_response_chars: int = 12000
    analysis_provider_health_checks_enabled: bool = True
    analysis_provider_health_check_interval_seconds: int = 300
    analysis_provider_health_check_batch_size: int = 10
    workflow_analysis_enabled: bool = False

    # ── News provider (Phase 2) ───────────────────────────────────────────────
    news_provider: str = "mock"
    news_api_key: str = ""
    news_max_age_minutes: float = 15.0
    news_official_timeout_sec: float = 10.0
    news_official_cache_minutes: float = 10.0
    volatility_provider: str = "mock"
    volatility_timeframe: str = "M15"
    volatility_atr_period: int = 14
    volatility_baseline_bars: int = 72
    volatility_abnormal_ratio: float = 2.0
    volatility_max_bar_age_minutes: float = 45.0

    # Read-only realtime watchlist data
    market_data_enabled: bool = True
    market_data_provider: str = "mt5"
    market_data_endpoint: str = "wss://stream.data.alpaca.markets/v2"
    market_data_feed: str = "iex"
    market_data_api_key_ref: str = "MARKET_DATA_ALPACA_KEY"
    market_data_api_secret_ref: str = "MARKET_DATA_ALPACA_SECRET"
    market_data_default_symbols: str = "XAUUSD"
    market_data_max_symbols: int = 25
    market_data_timeout_sec: float = 10.0
    market_data_allowed_hosts: str = "stream.data.alpaca.markets"

    @field_validator("mt5_bridge_type")
    @classmethod
    def _check_bridge_type(cls, v: str) -> str:
        allowed = {"mock", "ea_socket"}
        if v not in allowed:
            raise ValueError(f"MT5_BRIDGE_TYPE must be one of {allowed}, got {v!r}")
        return v

    @field_validator("volatility_provider")
    @classmethod
    def _check_volatility_provider(cls, v: str) -> str:
        allowed = {"mock", "mt5"}
        if v not in allowed:
            raise ValueError(f"VOLATILITY_PROVIDER must be one of {allowed}, got {v!r}")
        return v

    @field_validator("news_provider")
    @classmethod
    def _check_news_provider(cls, v: str) -> str:
        allowed = {"mock", "routed_mcp", "official_us"}
        if v not in allowed:
            raise ValueError(f"NEWS_PROVIDER must be one of {allowed}, got {v!r}")
        return v

    # ── Derived helpers ───────────────────────────────────────────────────────
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def mcp_allowed_host_list(self) -> list[str]:
        return [host.strip().lower() for host in self.mcp_allowed_hosts.split(",") if host.strip()]

    @property
    def analysis_provider_allowed_host_list(self) -> list[str]:
        return [
            host.strip().lower()
            for host in self.analysis_provider_allowed_hosts.split(",")
            if host.strip()
        ]

    @property
    def openai_provider_allowed_host_list(self) -> list[str]:
        return [
            host.strip().lower()
            for host in self.openai_provider_allowed_hosts.split(",")
            if host.strip()
        ]

    @property
    def market_data_allowed_host_list(self) -> list[str]:
        return [
            host.strip().lower()
            for host in self.market_data_allowed_hosts.split(",")
            if host.strip()
        ]

    @property
    def market_data_default_symbol_list(self) -> list[str]:
        return [
            symbol.strip().upper()
            for symbol in self.market_data_default_symbols.split(",")
            if symbol.strip()
        ]

    @property
    def effective_database_url(self) -> str:
        """SQLite file by default in dev; explicit DATABASE_URL otherwise."""
        return self.database_url or "sqlite:///./trader_dev.db"

    def auto_real_full_enabled(self) -> bool:
        """AUTO_REAL_FULL only counts as enabled when *every* guard agrees.

        This is intentionally an AND of several independent flags so that no
        single boolean can flip the system into placing automatic real orders.
        """
        return (
            self.trading_mode is TradingMode.AUTO_REAL_FULL
            and self.allow_real_trading
            and self.allow_auto_real_full
            and not self.emergency_stop
        )

    def validate_safety(self) -> list[str]:
        """Return a list of configuration problems; empty list means OK.

        Any non-empty result is treated as "config missing/invalid" by the
        order chokepoint and causes a BLOCK.
        """
        problems: list[str] = []
        if self.risk_max_risk_per_trade_pct <= 0:
            problems.append("RISK_MAX_RISK_PER_TRADE_PCT must be > 0")
        if self.risk_max_portfolio_risk_pct <= 0:
            problems.append("RISK_MAX_PORTFOLIO_RISK_PCT must be > 0")
        if self.risk_daily_max_loss_pct <= 0:
            problems.append("RISK_DAILY_MAX_LOSS_PCT must be > 0")
        if self.risk_max_trades_per_day <= 0:
            problems.append("RISK_MAX_TRADES_PER_DAY must be > 0")
        if self.risk_max_open_positions <= 0:
            problems.append("RISK_MAX_OPEN_POSITIONS must be > 0")
        if self.risk_max_spread_points <= 0:
            problems.append("RISK_MAX_SPREAD_POINTS must be > 0")
        if self.risk_min_free_margin_pct <= 0:
            problems.append("RISK_MIN_FREE_MARGIN_PCT must be > 0")
        if self.risk_max_order_volume_lots <= 0:
            problems.append("RISK_MAX_ORDER_VOLUME_LOTS must be > 0")
        if self.mt5_heartbeat_max_age_sec <= 0:
            problems.append("MT5_HEARTBEAT_MAX_AGE_SEC must be > 0")
        if self.mt5_bridge_type == "ea_socket" and not self.mt5_ea_shared_secret:
            problems.append("MT5_EA_SHARED_SECRET is required for ea_socket")
        if self.bridge_retry_max_attempts < 1:
            problems.append("BRIDGE_RETRY_MAX_ATTEMPTS must be >= 1")
        if self.bridge_retry_backoff_base_sec < 0:
            problems.append("BRIDGE_RETRY_BACKOFF_BASE_SEC must be >= 0")
        if self.bridge_circuit_fail_threshold < 1:
            problems.append("BRIDGE_CIRCUIT_FAIL_THRESHOLD must be >= 1")
        if self.bridge_circuit_reset_sec < 0:
            problems.append("BRIDGE_CIRCUIT_RESET_SEC must be >= 0")
        if self.app_env.lower() == "prod" and not self.api_auth_required:
            problems.append("API_AUTH_REQUIRED must be true in production")
        if self.api_auth_required and not self.api_auth_token:
            problems.append("API_AUTH_TOKEN is required when API_AUTH_REQUIRED=true")
        if self.user_auth_enabled and self.auth_session_hours <= 0:
            problems.append("AUTH_SESSION_HOURS must be > 0")
        if self.user_auth_enabled and self.auth_max_failed_attempts < 1:
            problems.append("AUTH_MAX_FAILED_ATTEMPTS must be >= 1")
        if self.user_auth_enabled and self.auth_lock_minutes < 1:
            problems.append("AUTH_LOCK_MINUTES must be >= 1")
        if self.allow_real_trading and not self.api_auth_required:
            if not self.user_auth_enabled:
                problems.append(
                    "ALLOW_REAL_TRADING=true requires API_AUTH_REQUIRED=true "
                    "or USER_AUTH_ENABLED=true"
                )
        if self.workflow_interval_seconds < 5:
            problems.append("WORKFLOW_INTERVAL_SECONDS must be >= 5")
        if self.workflow_max_backoff_seconds < self.workflow_interval_seconds:
            problems.append(
                "WORKFLOW_MAX_BACKOFF_SECONDS must be >= WORKFLOW_INTERVAL_SECONDS"
            )
        if (
            self.workflow_auto_demo_enabled
            and self.trading_mode is not TradingMode.AUTO_DEMO
        ):
            problems.append(
                "WORKFLOW_AUTO_DEMO_ENABLED=true requires TRADING_MODE=AUTO_DEMO"
            )
        if self.approval_expiry_minutes <= 0:
            problems.append("APPROVAL_EXPIRY_MINUTES must be > 0")
        if self.reconciliation_expiry_minutes <= 0:
            problems.append("RECONCILIATION_EXPIRY_MINUTES must be > 0")
        if self.reconciliation_batch_size <= 0:
            problems.append("RECONCILIATION_BATCH_SIZE must be > 0")
        if self.strategy_d40_value <= 0 or self.strategy_d20_value <= 0:
            problems.append("STRATEGY_D40_VALUE and STRATEGY_D20_VALUE must be > 0")
        if self.strategy_reward_risk_ratio <= 0:
            problems.append("STRATEGY_REWARD_RISK_RATIO must be > 0")
        if not 0 < self.strategy_risk_pct <= self.risk_max_risk_per_trade_pct:
            problems.append(
                "STRATEGY_RISK_PCT must be > 0 and <= RISK_MAX_RISK_PER_TRADE_PCT"
            )
        if self.proposal_expiry_minutes <= 0:
            problems.append("PROPOSAL_EXPIRY_MINUTES must be > 0")
        if self.strategy_timeframe.upper() not in {
            "M1", "M5", "M15", "M30", "H1", "H4", "D1",
        }:
            problems.append("STRATEGY_TIMEFRAME must be one of M1/M5/M15/M30/H1/H4/D1")
        if self.volatility_timeframe.upper() not in {
            "M1", "M5", "M15", "M30", "H1", "H4", "D1",
        }:
            problems.append(
                "VOLATILITY_TIMEFRAME must be one of M1/M5/M15/M30/H1/H4/D1"
            )
        if self.volatility_atr_period < 2:
            problems.append("VOLATILITY_ATR_PERIOD must be >= 2")
        if self.volatility_baseline_bars < self.volatility_atr_period:
            problems.append(
                "VOLATILITY_BASELINE_BARS must be >= VOLATILITY_ATR_PERIOD"
            )
        if self.volatility_abnormal_ratio <= 1:
            problems.append("VOLATILITY_ABNORMAL_RATIO must be > 1")
        if self.volatility_max_bar_age_minutes <= 0:
            problems.append("VOLATILITY_MAX_BAR_AGE_MINUTES must be > 0")
        if self.news_max_age_minutes <= 0:
            problems.append("NEWS_MAX_AGE_MINUTES must be > 0")
        if self.news_official_timeout_sec <= 0:
            problems.append("NEWS_OFFICIAL_TIMEOUT_SEC must be > 0")
        if self.news_official_cache_minutes <= 0:
            problems.append("NEWS_OFFICIAL_CACHE_MINUTES must be > 0")
        if self.news_official_cache_minutes > self.news_max_age_minutes:
            problems.append(
                "NEWS_OFFICIAL_CACHE_MINUTES must be <= NEWS_MAX_AGE_MINUTES"
            )
        if self.mcp_max_discovered_tools < 1:
            problems.append("MCP_MAX_DISCOVERED_TOOLS must be >= 1")
        if self.analysis_provider_max_response_chars < 1000:
            problems.append("ANALYSIS_PROVIDER_MAX_RESPONSE_CHARS must be >= 1000")
        if self.analysis_provider_health_check_interval_seconds < 30:
            problems.append(
                "ANALYSIS_PROVIDER_HEALTH_CHECK_INTERVAL_SECONDS must be >= 30"
            )
        if not 1 <= self.analysis_provider_health_check_batch_size <= 100:
            problems.append(
                "ANALYSIS_PROVIDER_HEALTH_CHECK_BATCH_SIZE must be between 1 and 100"
            )
        # Inconsistent real-trading config is a safety problem, not a convenience.
        if self.allow_auto_real_full and not self.allow_real_trading:
            problems.append("ALLOW_AUTO_REAL_FULL=true requires ALLOW_REAL_TRADING=true")
        return problems


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Override in tests via dependency injection."""
    return Settings()
