"""D40/D20 idealized backtester — rule-consistency checks on synthetic candles."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.models import Candle
from app.strategy.backtest import backtest_donchian

_BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _c(i: int, *, o: float, h: float, low: float, c: float) -> Candle:
    return Candle(
        time=_BASE + timedelta(hours=i),
        open=o,
        high=h,
        low=low,
        close=c,
        volume=1000,
    )


def _flat(n: int) -> list[Candle]:
    return [_c(i, o=100.0, h=100.5, low=99.5, c=100.0) for i in range(n)]


def test_no_breakout_no_trades():
    result = backtest_donchian(_flat(10), d40=3, d20=2, reward_risk=2)
    assert result.trades == 0
    assert result.total_r == 0.0
    assert result.win_rate == 0.0


def test_buy_breakout_hitting_tp_is_a_win():
    candles = _flat(3)
    candles.append(_c(3, o=100.0, h=102.2, low=100.0, c=102.0))  # breaks 3-bar high 100.5
    candles.append(_c(4, o=102.0, h=108.0, low=101.0, c=107.0))  # high >= TP 107
    result = backtest_donchian(candles, d40=3, d20=2, reward_risk=2)

    assert result.trades == 1
    assert result.wins == 1 and result.losses == 0
    assert result.win_rate == 1.0
    assert result.total_r == 2.0
    assert result.avg_r == 2.0
    assert result.max_drawdown_r == 0.0
    trade = result.trade_log[0]
    assert trade.side == "BUY"
    assert trade.entry_price == 102.0
    assert trade.stop_loss == 99.5  # 2-bar channel low
    assert trade.take_profit == 107.0  # entry + 2 * (102 - 99.5)
    assert trade.outcome == "tp"


def test_buy_breakout_hitting_sl_is_a_loss():
    candles = _flat(3)
    candles.append(_c(3, o=100.0, h=102.2, low=100.0, c=102.0))
    candles.append(_c(4, o=102.0, h=102.0, low=99.0, c=99.5))  # low <= SL 99.5
    result = backtest_donchian(candles, d40=3, d20=2, reward_risk=2)

    assert result.trades == 1
    assert result.losses == 1 and result.wins == 0
    assert result.total_r == -1.0
    assert result.max_drawdown_r == 1.0
    assert result.trade_log[0].outcome == "sl"


def test_unresolved_trade_stays_open_and_is_excluded_from_stats():
    candles = _flat(3)
    candles.append(_c(3, o=100.0, h=102.2, low=100.0, c=102.0))
    candles.append(_c(4, o=102.0, h=103.0, low=101.0, c=102.5))  # neither TP nor SL
    result = backtest_donchian(candles, d40=3, d20=2, reward_risk=2)

    assert result.trades == 0  # closed only
    assert result.open_trades == 1
    assert result.total_r == 0.0
