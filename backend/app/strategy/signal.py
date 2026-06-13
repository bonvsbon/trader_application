"""XAUUSD D40/D20 Donchian breakout signal.

The rule is deliberately objective and free of discretion so it can be audited
and backtested:

    * Entry — the latest CLOSED bar closes above the highest high of the prior
      `d40` bars (BUY) or below the lowest low of those bars (SELL). Using closed
      bars only avoids repainting.
    * Stop loss — the opposite side of the `d20` Donchian channel (the classic
      Turtle exit doubling as the initial stop).
    * Take profit / volume — computed downstream by `ProposalService` from the
      preset's reward:risk ratio and risk %.

A signal NEVER reaches the broker on its own. It produces a trade *proposal*
that a human approves; the proposal still flows through the order chokepoint and
Risk Engine. Automatic generation stays gated behind
`signal_definition_confirmed` so the semantics can't silently go live.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.enums import OrderSide
from app.core.logging import get_logger
from app.domain.models import Candle
from app.persistence.entities import TradeProposalRow
from app.persistence.repositories import StrategyConfigRepository
from app.strategy.base import default_strategy_config
from app.strategy.proposals import ProposalService

logger = get_logger(__name__)


@dataclass(frozen=True)
class DonchianSignal:
    side: OrderSide
    breakout_level: float  # the channel level that was broken
    stop_loss: float
    candle_time: datetime
    reason: str


def evaluate_donchian(candles: list[Candle], d40: int, d20: int) -> DonchianSignal | None:
    """Pure evaluation. Returns a signal, or None when there is no breakout or
    not enough bars. `candles` is oldest-first and must be closed bars."""
    if d40 < 1 or d20 < 1:
        return None
    # Need the prior `d40` bars plus the latest closed bar to test a breakout.
    if len(candles) < d40 + 1:
        return None

    latest = candles[-1]
    entry_window = candles[-(d40 + 1):-1]  # the d40 bars before the latest
    stop_window = candles[-d20:]           # last d20 bars (incl. latest)

    highest = max(c.high for c in entry_window)
    lowest = min(c.low for c in entry_window)

    if latest.close > highest:
        sl = min(c.low for c in stop_window)
        if sl >= latest.close:  # degenerate; no usable risk distance
            return None
        return DonchianSignal(
            side=OrderSide.BUY,
            breakout_level=highest,
            stop_loss=sl,
            candle_time=latest.time,
            reason=f"Close {latest.close} broke {d40}-bar high {highest}; SL at {d20}-bar low {sl}",
        )
    if latest.close < lowest:
        sl = max(c.high for c in stop_window)
        if sl <= latest.close:
            return None
        return DonchianSignal(
            side=OrderSide.SELL,
            breakout_level=lowest,
            stop_loss=sl,
            candle_time=latest.time,
            reason=f"Close {latest.close} broke {d40}-bar low {lowest}; SL at {d20}-bar high {sl}",
        )
    return None


@dataclass(frozen=True)
class SignalResult:
    signal: DonchianSignal | None
    proposal: TradeProposalRow | None
    reason: str


class SignalService:
    """Evaluates the gated D40/D20 signal and, on a breakout, produces a
    proposal through the existing `ProposalService` (never the broker)."""

    def __init__(self, proposal_service: ProposalService) -> None:
        self.proposals = proposal_service
        self.order_service = proposal_service.order_service
        self.settings = proposal_service.settings
        self.strategy_configs = StrategyConfigRepository(
            proposal_service.session, self.order_service.mt5_account_id
        )

    def evaluate(self, *, created_by: str) -> SignalResult:
        config = self.strategy_configs.get_config() or default_strategy_config(self.settings)
        if not config.enabled:
            return SignalResult(None, None, "Strategy preset is disabled")
        if not config.signal_definition_confirmed:
            # Hard gate: automatic signal generation stays off until the operator
            # confirms the D40/D20 definition. Manual proposals are unaffected.
            return SignalResult(
                None, None,
                "Automatic signal generation is disabled "
                "(set signal_definition_confirmed to enable)",
            )

        d40, d20 = int(config.d40_value), int(config.d20_value)
        candles = self.order_service.bridge.candles(
            config.symbol, self.settings.strategy_timeframe, d40 + 2
        )
        signal = evaluate_donchian(candles, d40, d20)
        if signal is None:
            return SignalResult(None, None, "No D40/D20 breakout on the latest closed bar")

        candle_time = signal.candle_time
        if candle_time.tzinfo is None:
            candle_time = candle_time.replace(tzinfo=timezone.utc)
        candle_key = candle_time.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        order_key = (
            f"auto-signal-{config.symbol.lower()}-"
            f"{self.settings.strategy_timeframe.lower()}-{candle_key}"
        )
        existing = self.proposals.proposals.get_by_order_key(order_key)
        if existing is not None:
            return SignalResult(
                signal,
                existing,
                "Signal already has a proposal for this closed bar",
            )

        proposal = self.proposals.generate(
            side=signal.side,
            sl=signal.stop_loss,
            volume=None,
            strategy_reason=f"D40/D20 Donchian breakout — {signal.reason}",
            created_by=created_by,
            order_idempotency_key=order_key,
        )
        return SignalResult(signal, proposal, "Signal generated a trade proposal")
