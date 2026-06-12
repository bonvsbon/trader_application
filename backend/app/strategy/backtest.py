"""Idealized backtest of the D40/D20 Donchian rule over historical candles.

This is a **rule-consistency check, not a profitability forecast**. It assumes:

    * close-to-close entries on the bar that breaks out,
    * one position at a time (no pyramiding, no overlap),
    * a fixed reward:risk exit (TP) and the 20-bar channel stop (SL),
    * no spread, slippage, commission, swap, or partial fills,
    * if a single bar touches both SL and TP, the SL is assumed first
      (conservative).

Outcomes are expressed in **R-multiples** (TP = +reward_risk, SL = -1) so the
result is account-size independent and directly comparable to the realized R in
Trade History. Treat the numbers as a sanity check on the signal definition, not
investment advice — live behaviour will differ.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import OrderSide
from app.domain.models import Candle
from app.persistence.repositories import StrategyConfigRepository
from app.strategy.base import default_strategy_config
from app.strategy.signal import evaluate_donchian


@dataclass(frozen=True)
class BacktestTrade:
    side: str
    entry_index: int
    entry_price: float
    stop_loss: float
    take_profit: float
    exit_index: int | None
    exit_price: float | None
    outcome: str  # "tp" | "sl" | "open"
    r_multiple: float


@dataclass(frozen=True)
class BacktestResult:
    candles: int
    trades: int  # closed (resolved) trades
    wins: int
    losses: int
    open_trades: int
    win_rate: float
    total_r: float
    avg_r: float
    max_drawdown_r: float
    reward_risk: float
    d40: int
    d20: int
    trade_log: list[BacktestTrade]


def backtest_donchian(
    candles: list[Candle],
    d40: int,
    d20: int,
    reward_risk: float,
) -> BacktestResult:
    """Walk the bars forward, opening one position per breakout and resolving it
    against the fixed TP / channel SL before looking for the next signal."""
    n = len(candles)
    trades: list[BacktestTrade] = []

    # `evaluate_donchian` treats the last element it is given as the latest
    # closed bar, so passing candles[: k + 1] makes candles[k] that bar.
    k = d40
    while k < n:
        signal = evaluate_donchian(candles[: k + 1], d40, d20)
        if signal is None:
            k += 1
            continue

        entry = candles[k].close
        sl = signal.stop_loss
        risk = abs(entry - sl)
        if risk <= 0:
            k += 1
            continue
        tp = entry + risk * reward_risk if signal.side is OrderSide.BUY else entry - risk * reward_risk

        exit_index: int | None = None
        exit_price: float | None = None
        outcome = "open"
        r_multiple = 0.0

        j = k + 1
        while j < n:
            bar = candles[j]
            if signal.side is OrderSide.BUY:
                hit_sl, hit_tp = bar.low <= sl, bar.high >= tp
            else:
                hit_sl, hit_tp = bar.high >= sl, bar.low <= tp
            if hit_sl:  # conservative: SL wins a same-bar tie
                exit_index, exit_price, outcome, r_multiple = j, sl, "sl", -1.0
                break
            if hit_tp:
                exit_index, exit_price, outcome, r_multiple = j, tp, "tp", float(reward_risk)
                break
            j += 1

        trades.append(
            BacktestTrade(
                side=signal.side.value,
                entry_index=k,
                entry_price=round(entry, 2),
                stop_loss=round(sl, 2),
                take_profit=round(tp, 2),
                exit_index=exit_index,
                exit_price=round(exit_price, 2) if exit_price is not None else None,
                outcome=outcome,
                r_multiple=r_multiple,
            )
        )

        if exit_index is None:
            break  # still open at the end of the series; stop scanning
        k = exit_index + 1  # no overlapping positions

    closed = [t for t in trades if t.outcome in ("tp", "sl")]
    wins = sum(1 for t in closed if t.outcome == "tp")
    losses = sum(1 for t in closed if t.outcome == "sl")
    total_r = sum(t.r_multiple for t in closed)

    peak = equity = max_dd = 0.0
    for t in closed:
        equity += t.r_multiple
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    return BacktestResult(
        candles=n,
        trades=len(closed),
        wins=wins,
        losses=losses,
        open_trades=sum(1 for t in trades if t.outcome == "open"),
        win_rate=round(wins / len(closed), 4) if closed else 0.0,
        total_r=round(total_r, 3),
        avg_r=round(total_r / len(closed), 3) if closed else 0.0,
        max_drawdown_r=round(max_dd, 3),
        reward_risk=float(reward_risk),
        d40=d40,
        d20=d20,
        trade_log=trades,
    )


class BacktestService:
    """Runs the backtest against bridge candles for the current preset.

    Read-only analysis: it never creates a proposal or touches the broker, so it
    is not gated behind `signal_definition_confirmed`."""

    MIN_BARS = 5
    MAX_BARS = 5000

    def __init__(self, order_service) -> None:
        self.order_service = order_service
        self.settings = order_service.settings
        self.strategy_configs = StrategyConfigRepository(order_service.session)

    def run(self, *, count: int) -> BacktestResult:
        config = self.strategy_configs.get_config() or default_strategy_config(self.settings)
        d40, d20 = int(config.d40_value), int(config.d20_value)
        count = max(d40 + self.MIN_BARS, min(int(count), self.MAX_BARS))
        candles = self.order_service.bridge.candles(
            config.symbol, self.settings.strategy_timeframe, count
        )
        return backtest_donchian(candles, d40, d20, config.reward_risk_ratio)
