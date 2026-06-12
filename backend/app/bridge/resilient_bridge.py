"""Resilience decorator for the MT5 bridge: bounded retry + circuit breaker.

Wraps a raw transport bridge (the EA socket adapter) so that transient read
failures are retried with capped, jittered backoff, and a run of failures
"opens" a circuit that fails fast instead of stalling every call on a socket
timeout.

Two safety invariants are deliberate and must not be relaxed:

* ``execute_order`` is NEVER retried. Re-sending an order whose outcome is
  unknown risks a double position. A failed execution still propagates so the
  order chokepoint can mark it RECONCILIATION_REQUIRED.
* ``health`` always passes straight through, even when the circuit is open.
  Health is how recovery is detected; gating it would latch the bridge off.

Only idempotent reads (account_info, quote, symbol_info, positions,
closed_trades_today, order_status) are retried and gated by the breaker.
"""

from __future__ import annotations

import random
import threading
import time
from datetime import datetime
from collections.abc import Callable
from enum import Enum
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.errors import BridgeUnavailableError
from app.domain.models import (
    AccountInfo,
    BridgeHealthStatus,
    ClosedTrade,
    OrderRequest,
    Position,
    SymbolInfo,
    SymbolQuote,
)
from app.domain.ports import MT5BridgePort

logger = get_logger(__name__)

# Transient transport problems worth a retry. Malformed-protocol errors are
# already wrapped as BridgeUnavailableError by the socket adapter.
_TRANSIENT: tuple[type[Exception], ...] = (BridgeUnavailableError, OSError)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class ResilientBridge:
    """Decorates a bridge with retry + circuit breaker on idempotent reads."""

    def __init__(
        self,
        bridge: MT5BridgePort,
        *,
        max_attempts: int = 2,
        backoff_base_sec: float = 0.2,
        backoff_max_sec: float = 2.0,
        circuit_fail_threshold: int = 5,
        circuit_reset_sec: float = 30.0,
        sleep: Callable[[float], Any] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.bridge = bridge
        self.max_attempts = max(1, max_attempts)
        self.backoff_base_sec = max(0.0, backoff_base_sec)
        self.backoff_max_sec = max(0.0, backoff_max_sec)
        self.circuit_fail_threshold = max(1, circuit_fail_threshold)
        self.circuit_reset_sec = max(0.0, circuit_reset_sec)
        self._sleep = sleep
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = 0.0

    @classmethod
    def from_settings(
        cls, bridge: MT5BridgePort, settings: Settings | None = None
    ) -> "ResilientBridge":
        settings = settings or get_settings()
        return cls(
            bridge,
            max_attempts=settings.bridge_retry_max_attempts,
            backoff_base_sec=settings.bridge_retry_backoff_base_sec,
            backoff_max_sec=settings.bridge_retry_backoff_max_sec,
            circuit_fail_threshold=settings.bridge_circuit_fail_threshold,
            circuit_reset_sec=settings.bridge_circuit_reset_sec,
        )

    # ── Circuit breaker bookkeeping ──────────────────────────────────────────
    @property
    def circuit_state(self) -> CircuitState:
        with self._lock:
            return self._state

    def _before_call(self) -> None:
        """Fail fast if the circuit is open and its cooldown has not elapsed.

        After the cooldown the circuit moves to HALF_OPEN and the caller is
        allowed a single trial call.
        """
        with self._lock:
            if self._state is CircuitState.OPEN:
                if self._monotonic() - self._opened_at >= self.circuit_reset_sec:
                    self._state = CircuitState.HALF_OPEN
                    logger.info("MT5 bridge circuit half-open; allowing a trial call")
                else:
                    raise BridgeUnavailableError(
                        "MT5 bridge circuit is open after repeated failures"
                    )

    def _record_success(self) -> None:
        with self._lock:
            if self._state is not CircuitState.CLOSED:
                logger.info("MT5 bridge circuit closed after a successful call")
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0

    def _record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            trip = (
                self._state is CircuitState.HALF_OPEN
                or self._consecutive_failures >= self.circuit_fail_threshold
            )
            if trip:
                if self._state is not CircuitState.OPEN:
                    logger.warning(
                        "MT5 bridge circuit opened after %d consecutive failure(s)",
                        self._consecutive_failures,
                    )
                self._state = CircuitState.OPEN
                self._opened_at = self._monotonic()

    def _backoff(self, attempt: int) -> float:
        delay = min(self.backoff_max_sec, self.backoff_base_sec * (2**attempt))
        if delay <= 0:
            return 0.0
        # Jitter to 50–100% of the computed delay to avoid synchronized retries.
        return delay * (0.5 + random.random() / 2.0)

    def _call_read(self, name: str, *args: Any, **kwargs: Any) -> Any:
        method = getattr(self.bridge, name)
        self._before_call()
        for attempt in range(self.max_attempts):
            try:
                result = method(*args, **kwargs)
            except _TRANSIENT:
                self._record_failure()
                last_attempt = attempt + 1 >= self.max_attempts
                if last_attempt or self.circuit_state is CircuitState.OPEN:
                    raise
                self._sleep(self._backoff(attempt))
            else:
                self._record_success()
                return result
        raise AssertionError("unreachable")  # pragma: no cover

    # ── MT5BridgePort surface ────────────────────────────────────────────────
    def health(self) -> BridgeHealthStatus:
        # Always allowed, never retried: health is the recovery signal and the
        # adapter already reports failures as a status rather than raising.
        return self.bridge.health()

    def account_info(self) -> AccountInfo:
        return self._call_read("account_info")

    def quote(self, symbol: str) -> SymbolQuote:
        return self._call_read("quote", symbol)

    def symbol_info(self, symbol: str) -> SymbolInfo:
        return self._call_read("symbol_info", symbol)

    def candles(self, symbol: str, timeframe: str, count: int):
        return self._call_read("candles", symbol, timeframe, count)

    def positions(self) -> list[Position]:
        return self._call_read("positions")

    def closed_trades_today(self) -> list[ClosedTrade]:
        return self._call_read("closed_trades_today")

    def closed_trades_range(self, start: datetime, end: datetime) -> list[ClosedTrade]:
        return self._call_read("closed_trades_range", start, end)

    def order_status(self, idempotency_key: str) -> dict | None:
        return self._call_read("order_status", idempotency_key)

    def execute_order(self, request: OrderRequest) -> dict:
        # NEVER retried: a single attempt only. The outcome of a failed send is
        # unknown, so the chokepoint must reconcile rather than resubmit. We
        # still feed the breaker so reads start failing fast when the bridge is
        # clearly down.
        try:
            result = self.bridge.execute_order(request)
        except _TRANSIENT:
            self._record_failure()
            raise
        self._record_success()
        return result

    def close(self) -> None:
        close = getattr(self.bridge, "close", None)
        if callable(close):
            close()
