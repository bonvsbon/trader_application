"""Port interfaces (hexagonal architecture).

Adapters implement these Protocols; the application core depends only on the
ports, never on a concrete adapter. This is what keeps MT5/AI/news/strategy code
out of the risk and execution layers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.domain.models import (
    AccountInfo,
    BridgeHealthStatus,
    Candle,
    ClosedTrade,
    NewsRisk,
    OrderRequest,
    Position,
    SymbolInfo,
    SymbolQuote,
    VolatilityRisk,
)


@runtime_checkable
class MT5BridgePort(Protocol):
    """Connection to MetaTrader 5. The mock adapter implements this in Phase 1.

    Only `execution.order_service` is allowed to call `execute_order`.
    """

    def health(self) -> BridgeHealthStatus: ...

    def account_info(self) -> AccountInfo: ...

    def quote(self, symbol: str) -> SymbolQuote: ...

    def symbol_info(self, symbol: str) -> SymbolInfo: ...

    def candles(self, symbol: str, timeframe: str, count: int) -> list[Candle]:
        """Most recent `count` closed OHLC bars for `symbol` at `timeframe`,
        oldest first. Read-only; powers rule-based signals (e.g. Donchian)."""
        ...

    def positions(self) -> list[Position]: ...

    def closed_trades_today(self) -> list[ClosedTrade]: ...

    def closed_trades_range(self, start: datetime, end: datetime) -> list[ClosedTrade]:
        """Closed trades whose close time falls within [start, end] — for the
        historical backfill. Idempotent and read-only."""
        ...

    def order_status(self, idempotency_key: str) -> dict | None: ...

    def execute_order(self, request: OrderRequest) -> dict:
        """Send an order to MT5 and return the raw broker response dict."""
        ...


@runtime_checkable
class StrategyPort(Protocol):
    """A trading strategy. Phase 2 implements the XAUUSD D40/D20 preset."""

    name: str

    def evaluate(self, symbol: str, quote: SymbolQuote | None) -> dict: ...


@runtime_checkable
class AIProviderPort(Protocol):
    """An AI analysis provider. Never a safety layer — advisory only."""

    name: str

    def analyze(self, prompt: str, context: dict) -> dict: ...


@runtime_checkable
class NewsProviderPort(Protocol):
    """Economic calendar / news risk provider."""

    name: str

    def news_risk(self, symbol: str) -> NewsRisk: ...


@runtime_checkable
class VolatilityProviderPort(Protocol):
    """Market volatility/session provider."""

    name: str

    def volatility_risk(self, symbol: str) -> VolatilityRisk: ...
