"""Process-wide MT5 bridge manager with a persisted account allowlist."""

from __future__ import annotations

import ipaddress
import threading
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, get_settings
from app.core.enums import AccountType, BridgeHealth
from app.domain.errors import BridgeUnavailableError
from app.domain.models import (
    AccountInfo,
    BridgeHealthStatus,
    Candle,
    ClosedTrade,
    Mt5RuntimeConfig,
    OrderRequest,
    Position,
    SymbolInfo,
    SymbolQuote,
)
from app.domain.ports import MT5BridgePort


def default_mt5_config(settings: Settings | None = None) -> Mt5RuntimeConfig:
    settings = settings or get_settings()
    expected_type = settings.mt5_expected_account_type
    if settings.mt5_bridge_type == "mock" and expected_type is AccountType.UNKNOWN:
        expected_type = settings.mock_account_type
    return Mt5RuntimeConfig(
        enabled=True,
        bridge_type=settings.mt5_bridge_type,
        host=settings.mt5_ea_host,
        port=settings.mt5_ea_port,
        timeout_sec=settings.mt5_bridge_timeout_sec,
        heartbeat_max_age_sec=settings.mt5_heartbeat_max_age_sec,
        expected_login=settings.mt5_expected_login,
        expected_server=settings.mt5_expected_server or None,
        expected_account_type=expected_type,
    )


class UnavailableBridge:
    def __init__(self, detail: str) -> None:
        self.detail = detail

    def health(self) -> BridgeHealthStatus:
        return BridgeHealthStatus(health=BridgeHealth.UNKNOWN, detail=self.detail)

    def account_info(self) -> AccountInfo:
        return AccountInfo(account_type=AccountType.UNKNOWN)

    def _raise(self):
        raise BridgeUnavailableError(self.detail)

    def quote(self, symbol: str) -> SymbolQuote:
        self._raise()

    def symbol_info(self, symbol: str) -> SymbolInfo:
        self._raise()

    def candles(self, symbol: str, timeframe: str, count: int) -> list[Candle]:
        self._raise()

    def positions(self) -> list[Position]:
        self._raise()

    def closed_trades_today(self) -> list[ClosedTrade]:
        self._raise()

    def closed_trades_range(self, start: datetime, end: datetime) -> list[ClosedTrade]:
        self._raise()

    def order_status(self, idempotency_key: str) -> dict | None:
        self._raise()

    def execute_order(self, request: OrderRequest) -> dict:
        self._raise()


class AccountGuardBridge:
    """Blocks trading unless the connected terminal matches the configured account."""

    def __init__(self, bridge: MT5BridgePort, config: Mt5RuntimeConfig) -> None:
        self.bridge = bridge
        self.config = config
        self.heartbeat_max_age_sec = config.heartbeat_max_age_sec

    def health(self) -> BridgeHealthStatus:
        status = self.bridge.health()
        heartbeat = status.last_heartbeat
        if status.health is BridgeHealth.HEALTHY and heartbeat is not None:
            if heartbeat.tzinfo is None:
                heartbeat = heartbeat.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - heartbeat).total_seconds()
            if age > self.config.heartbeat_max_age_sec or age < -self.config.heartbeat_max_age_sec:
                return status.model_copy(
                    update={
                        "health": BridgeHealth.UNKNOWN,
                        "detail": f"MT5 heartbeat outside configured age limit ({age:.1f}s)",
                    }
                )
        return status

    def account_snapshot(self) -> tuple[AccountInfo, list[str]]:
        account = self.bridge.account_info()
        return account, self.config.account_problems(account)

    def account_info(self) -> AccountInfo:
        account, problems = self.account_snapshot()
        if problems:
            return account.model_copy(update={"account_type": AccountType.UNKNOWN})
        return account

    def quote(self, symbol: str) -> SymbolQuote:
        return self.bridge.quote(symbol)

    def symbol_info(self, symbol: str) -> SymbolInfo:
        return self.bridge.symbol_info(symbol)

    def candles(self, symbol: str, timeframe: str, count: int) -> list[Candle]:
        return self.bridge.candles(symbol, timeframe, count)

    def positions(self) -> list[Position]:
        return self.bridge.positions()

    def closed_trades_today(self) -> list[ClosedTrade]:
        return self.bridge.closed_trades_today()

    def closed_trades_range(self, start: datetime, end: datetime) -> list[ClosedTrade]:
        return self.bridge.closed_trades_range(start, end)

    def order_status(self, idempotency_key: str) -> dict | None:
        return self.bridge.order_status(idempotency_key)

    def execute_order(self, request: OrderRequest) -> dict:
        return self.bridge.execute_order(request)

    def close(self) -> None:
        close = getattr(self.bridge, "close", None)
        if callable(close):
            close()


def create_bridge(
    settings: Settings | None = None,
    config: Mt5RuntimeConfig | None = None,
) -> MT5BridgePort:
    settings = settings or get_settings()
    config = config or default_mt5_config(settings)
    if not config.enabled:
        return UnavailableBridge("MT5 configuration is disabled")
    if config.bridge_type == "ea_socket":
        from app.bridge.ea_socket_bridge import EaSocketBridge
        from app.bridge.resilient_bridge import ResilientBridge

        if not settings.mt5_ea_shared_secret:
            raise ValueError("MT5_EA_SHARED_SECRET is required for ea_socket")
        try:
            is_loopback = ipaddress.ip_address(config.host).is_loopback
        except ValueError:
            is_loopback = config.host.casefold() == "localhost"
        if not is_loopback and not settings.mt5_ea_allow_remote_bind:
            raise ValueError(
                "Remote MT5 EA bind requires MT5_EA_ALLOW_REMOTE_BIND=true"
            )
        # Wrap the transport in retry + circuit breaker so transient socket
        # failures don't stall every read; execute_order remains single-attempt.
        raw_bridge: MT5BridgePort = ResilientBridge.from_settings(
            EaSocketBridge(
                host=config.host,
                port=config.port,
                timeout=config.timeout_sec,
                shared_secret=settings.mt5_ea_shared_secret,
            ),
            settings,
        )
    else:
        from app.bridge.mock_bridge import MockBridge

        raw_bridge = MockBridge(settings=settings)
    return AccountGuardBridge(raw_bridge, config)


_bridge_lock = threading.RLock()
_bridge: MT5BridgePort | None = None
_runtime_config: Mt5RuntimeConfig | None = None


def _load_persisted_config() -> Mt5RuntimeConfig:
    try:
        from app.persistence.db import SessionLocal
        from app.persistence.repositories import Mt5ConfigRepository

        with SessionLocal() as session:
            return Mt5ConfigRepository(session).get_config() or default_mt5_config()
    except SQLAlchemyError:
        return default_mt5_config()


def get_effective_mt5_config() -> Mt5RuntimeConfig:
    global _runtime_config
    with _bridge_lock:
        if _runtime_config is None:
            _runtime_config = _load_persisted_config()
        return _runtime_config.model_copy()


def get_configured_bridge() -> MT5BridgePort:
    global _bridge
    with _bridge_lock:
        if _bridge is None:
            config = get_effective_mt5_config()
            try:
                _bridge = create_bridge(get_settings(), config)
            except Exception as exc:
                _bridge = UnavailableBridge(f"Could not start MT5 bridge: {exc}")
        return _bridge


def replace_configured_bridge(config: Mt5RuntimeConfig) -> MT5BridgePort:
    global _bridge, _runtime_config
    with _bridge_lock:
        previous = _bridge
        _bridge = None
        _runtime_config = config.model_copy()
        if previous is not None:
            close = getattr(previous, "close", None)
            if callable(close):
                close()
        try:
            _bridge = create_bridge(get_settings(), config)
        except Exception as exc:
            _bridge = UnavailableBridge(f"Could not start MT5 bridge: {exc}")
        return _bridge


def close_configured_bridge() -> None:
    global _bridge
    with _bridge_lock:
        bridge = _bridge
        _bridge = None
        if bridge is not None:
            close = getattr(bridge, "close", None)
            if callable(close):
                close()
