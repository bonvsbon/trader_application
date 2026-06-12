"""Mock MT5 bridge — the Phase 1 default.

Deterministic, in-process, no network. Health and account type are configurable
(via env `MOCK_BRIDGE_HEALTH` / `MOCK_ACCOUNT_TYPE`, or constructor args in tests)
so every safety branch — healthy/unhealthy, demo/real/unknown — can be exercised.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from itertools import count

from app.core.config import Settings, get_settings
from app.core.enums import AccountType, BridgeHealth, OrderSide
from app.domain.models import (
    AccountInfo,
    BridgeHealthStatus,
    Candle,
    ClosedTrade,
    OrderRequest,
    Position,
    SymbolInfo,
    SymbolQuote,
)

# Bar duration per timeframe label, for synthesizing candle timestamps.
_TIMEFRAME_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "D1": 86400,
}

# Rough reference price so XAUUSD quotes look sane in the UI.
_REFERENCE_PRICES = {"XAUUSD": 2350.0}
_SYMBOL_INFO = {
    "XAUUSD": SymbolInfo(
        symbol="XAUUSD",
        tick_size=0.01,
        tick_value=1.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )
}


class MockBridge:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        health: BridgeHealth | None = None,
        account_type: AccountType | None = None,
        account: AccountInfo | None = None,
        positions: list[Position] | None = None,
        closed_trades: list[ClosedTrade] | None = None,
        candles: list[Candle] | None = None,
        fail_execute: bool = False,
        fail_quote: bool = False,
        fail_positions: bool = False,
        fail_closed_trades: bool = False,
        fail_symbol_info: bool = False,
        execute_response: dict | None = None,
        order_status_response: dict | None = None,
        heartbeat_age_seconds: float = 0.0,
        spread_points: float = 20.0,
    ) -> None:
        s = settings or get_settings()
        self._health = health or (
            BridgeHealth.HEALTHY if s.mock_bridge_health.lower() == "healthy" else BridgeHealth.UNHEALTHY
        )
        self._account_type = account_type or s.mock_account_type
        self._account = account
        self._positions = positions if positions is not None else []
        self._closed_trades = closed_trades if closed_trades is not None else []
        self._candles = candles
        self._fail_execute = fail_execute
        self._fail_quote = fail_quote
        self._fail_positions = fail_positions
        self._fail_closed_trades = fail_closed_trades
        self._fail_symbol_info = fail_symbol_info
        self._execute_response = execute_response
        self._order_status_response = order_status_response
        self._heartbeat_age_seconds = heartbeat_age_seconds
        self._spread_points = spread_points
        self._tickets = count(1_000_001)
        self._orders_by_key: dict[str, dict] = {}

    def health(self) -> BridgeHealthStatus:
        return BridgeHealthStatus(
            health=self._health,
            last_heartbeat=datetime.now(timezone.utc) - timedelta(seconds=self._heartbeat_age_seconds),
            detail="mock bridge",
        )

    def account_info(self) -> AccountInfo:
        if self._account is not None:
            return self._account.model_copy()
        return AccountInfo(
            account_type=self._account_type,
            login=1_000_001,
            server="Mock-Server",
            currency="USD",
            balance=10_000.0,
            equity=10_000.0,
            margin=0.0,
            free_margin=10_000.0,
            leverage=100,
        )

    def quote(self, symbol: str) -> SymbolQuote:
        if self._fail_quote:
            raise ConnectionError("mock bridge: simulated quote failure")
        mid = _REFERENCE_PRICES.get(symbol.upper(), 100.0)
        half = self._spread_points / 200.0  # points -> price (mock scaling)
        return SymbolQuote(
            symbol=symbol,
            bid=round(mid - half, 2),
            ask=round(mid + half, 2),
            spread_points=self._spread_points,
            time=datetime.now(timezone.utc),
        )

    def positions(self) -> list[Position]:
        if self._fail_positions:
            raise ConnectionError("mock bridge: simulated positions failure")
        return list(self._positions)

    def symbol_info(self, symbol: str) -> SymbolInfo:
        if self._fail_symbol_info:
            raise ConnectionError("mock bridge: simulated symbol-info failure")
        info = _SYMBOL_INFO.get(symbol.upper())
        if info is None:
            raise ValueError(f"mock bridge: unsupported symbol {symbol}")
        return info.model_copy()

    def candles(self, symbol: str, timeframe: str, count: int) -> list[Candle]:
        if self._candles is not None:
            return [c.model_copy() for c in self._candles[-count:]]
        # Deterministic synthetic wave around the reference price so rule-based
        # signals have stable, reproducible bars to evaluate against.
        mid = _REFERENCE_PRICES.get(symbol.upper(), 100.0)
        step = _TIMEFRAME_SECONDS.get(timeframe.upper(), 3600)
        amplitude = mid * 0.01
        now = datetime.now(timezone.utc)
        bars: list[Candle] = []
        for i in range(count):
            base = mid + amplitude * math.sin(i / 7.0)
            nxt = mid + amplitude * math.sin((i + 1) / 7.0)
            o, c = base, nxt
            bars.append(
                Candle(
                    time=now - timedelta(seconds=step * (count - i)),
                    open=round(o, 2),
                    high=round(max(o, c) + amplitude * 0.1, 2),
                    low=round(min(o, c) - amplitude * 0.1, 2),
                    close=round(c, 2),
                    volume=1000.0,
                )
            )
        return bars

    def closed_trades_today(self) -> list[ClosedTrade]:
        if self._fail_closed_trades:
            raise ConnectionError("mock bridge: simulated closed-trades failure")
        return [trade.model_copy() for trade in self._closed_trades]

    def closed_trades_range(self, start: datetime, end: datetime) -> list[ClosedTrade]:
        if self._fail_closed_trades:
            raise ConnectionError("mock bridge: simulated closed-trades failure")
        out: list[ClosedTrade] = []
        for trade in self._closed_trades:
            ts = trade.close_time
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if start <= ts <= end:
                out.append(trade.model_copy())
        return out

    def order_status(self, idempotency_key: str) -> dict | None:
        response = self._order_status_response or self._orders_by_key.get(idempotency_key)
        return dict(response) if response is not None else None

    def execute_order(self, request: OrderRequest) -> dict:
        if self._fail_execute:
            raise ConnectionError("mock bridge: simulated execution failure")
        if self._execute_response is not None:
            response = dict(self._execute_response)
            self._orders_by_key[request.idempotency_key] = response
            return response
        q = self.quote(request.symbol)
        price = q.ask if request.side is OrderSide.BUY else q.bid
        response = {
            "ticket": next(self._tickets),
            "retcode": 10009,  # TRADE_RETCODE_DONE
            "retcode_text": "Request completed",
            "symbol": request.symbol,
            "side": request.side.value,
            "volume": request.volume,
            "price": price,
            "sl": request.sl,
            "tp": request.tp,
            "comment": "mock filled",
            "time": datetime.now(timezone.utc).isoformat(),
        }
        self._orders_by_key[request.idempotency_key] = response
        return response
