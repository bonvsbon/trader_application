"""ResilientBridge: bounded retry + circuit breaker on idempotent reads.

These tests pin the two safety invariants — execute_order is never retried, and
health always passes through even when the circuit is open — alongside the
retry/open/half-open/close lifecycle.
"""

from __future__ import annotations

import collections
from datetime import datetime, timezone

import pytest

from app.bridge.resilient_bridge import CircuitState, ResilientBridge
from app.core.enums import BridgeHealth, OrderSide
from app.domain.errors import BridgeUnavailableError
from app.domain.models import BridgeHealthStatus, OrderRequest, SymbolQuote
from app.domain.ports import MT5BridgePort


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class FlakyBridge:
    """Raises the first N calls of each named method, then succeeds."""

    def __init__(self, fail_plan: dict[str, int] | None = None) -> None:
        self.fail_plan = dict(fail_plan or {})
        self.calls: collections.Counter[str] = collections.Counter()

    def _maybe_fail(self, name: str) -> None:
        self.calls[name] += 1
        remaining = self.fail_plan.get(name, 0)
        if remaining > 0:
            self.fail_plan[name] = remaining - 1
            raise BridgeUnavailableError(f"{name} transient failure")

    def health(self) -> BridgeHealthStatus:
        self.calls["health"] += 1
        return BridgeHealthStatus(
            health=BridgeHealth.HEALTHY,
            last_heartbeat=datetime.now(timezone.utc),
        )

    def account_info(self):  # pragma: no cover - not exercised here
        self._maybe_fail("account_info")

    def quote(self, symbol: str) -> SymbolQuote:
        self._maybe_fail("quote")
        return SymbolQuote(
            symbol=symbol, bid=1.0, ask=2.0, spread_points=1.0,
            time=datetime.now(timezone.utc),
        )

    def symbol_info(self, symbol: str):  # pragma: no cover
        self._maybe_fail("symbol_info")

    def positions(self):  # pragma: no cover
        self._maybe_fail("positions")
        return []

    def closed_trades_today(self):  # pragma: no cover
        self._maybe_fail("closed_trades_today")
        return []

    def order_status(self, idempotency_key: str):
        self._maybe_fail("order_status")
        return None

    def execute_order(self, request: OrderRequest) -> dict:
        self._maybe_fail("execute_order")
        return {"retcode": 10009, "ticket": 1}

    def close(self) -> None:
        self.calls["close"] += 1


def _order() -> OrderRequest:
    return OrderRequest(
        symbol="XAUUSD", side=OrderSide.BUY, volume=0.1, sl=2349.0,
        risk_pct=1.0, idempotency_key="resilient-test-1",
    )


def _bridge(inner: FlakyBridge, clock: FakeClock | None = None, **kw) -> ResilientBridge:
    clock = clock or FakeClock()
    params = dict(
        max_attempts=1, backoff_base_sec=0.0, circuit_fail_threshold=3,
        circuit_reset_sec=30.0, sleep=lambda *_: None, monotonic=clock,
    )
    params.update(kw)
    return ResilientBridge(inner, **params)


def test_satisfies_bridge_port():
    assert isinstance(_bridge(FlakyBridge()), MT5BridgePort)


def test_read_retries_transient_then_succeeds():
    inner = FlakyBridge({"quote": 1})
    rb = _bridge(inner, max_attempts=2)
    assert rb.quote("XAUUSD").symbol == "XAUUSD"
    assert inner.calls["quote"] == 2  # one failure + one success
    assert rb.circuit_state is CircuitState.CLOSED


def test_circuit_opens_then_fast_fails_without_touching_bridge():
    inner = FlakyBridge({"quote": 999})
    rb = _bridge(inner, circuit_fail_threshold=3)
    for _ in range(3):
        with pytest.raises(BridgeUnavailableError):
            rb.quote("XAUUSD")
    assert rb.circuit_state is CircuitState.OPEN
    before = inner.calls["quote"]
    with pytest.raises(BridgeUnavailableError):
        rb.quote("XAUUSD")  # fast fail — underlying must not be called
    assert inner.calls["quote"] == before


def test_circuit_half_opens_after_cooldown_then_closes_on_success():
    inner = FlakyBridge({"quote": 3})  # first 3 fail, 4th succeeds
    clock = FakeClock()
    rb = _bridge(inner, clock=clock, circuit_fail_threshold=3, circuit_reset_sec=30.0)
    for _ in range(3):
        with pytest.raises(BridgeUnavailableError):
            rb.quote("XAUUSD")
    assert rb.circuit_state is CircuitState.OPEN
    clock.advance(31.0)
    assert rb.quote("XAUUSD").symbol == "XAUUSD"  # half-open trial succeeds
    assert rb.circuit_state is CircuitState.CLOSED


def test_half_open_failure_reopens_circuit():
    inner = FlakyBridge({"quote": 999})
    clock = FakeClock()
    rb = _bridge(inner, clock=clock, circuit_fail_threshold=2, circuit_reset_sec=30.0)
    for _ in range(2):
        with pytest.raises(BridgeUnavailableError):
            rb.quote("XAUUSD")
    assert rb.circuit_state is CircuitState.OPEN
    clock.advance(31.0)
    with pytest.raises(BridgeUnavailableError):
        rb.quote("XAUUSD")  # half-open trial fails -> reopen immediately
    assert rb.circuit_state is CircuitState.OPEN


def test_execute_order_is_never_retried():
    inner = FlakyBridge({"execute_order": 999})
    rb = _bridge(inner, max_attempts=5)
    with pytest.raises(BridgeUnavailableError):
        rb.execute_order(_order())
    assert inner.calls["execute_order"] == 1  # exactly one attempt


def test_health_passes_through_even_when_circuit_open():
    inner = FlakyBridge({"quote": 999})
    rb = _bridge(inner, circuit_fail_threshold=2)
    for _ in range(2):
        with pytest.raises(BridgeUnavailableError):
            rb.quote("XAUUSD")
    assert rb.circuit_state is CircuitState.OPEN
    assert rb.health().health is BridgeHealth.HEALTHY


def test_successful_execute_resets_failure_streak():
    inner = FlakyBridge({"quote": 1})  # one read failure, below threshold
    rb = _bridge(inner, circuit_fail_threshold=3)
    with pytest.raises(BridgeUnavailableError):
        rb.quote("XAUUSD")
    rb.execute_order(_order())  # success clears the streak
    inner.fail_plan["quote"] = 2  # two more failures, still under threshold of 3
    for _ in range(2):
        with pytest.raises(BridgeUnavailableError):
            rb.quote("XAUUSD")
    assert rb.circuit_state is CircuitState.CLOSED


def test_close_delegates_to_wrapped_bridge():
    inner = FlakyBridge()
    _bridge(inner).close()
    assert inner.calls["close"] == 1
