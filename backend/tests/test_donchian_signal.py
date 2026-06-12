"""D40/D20 Donchian breakout: pure evaluator + gated SignalService.

The signal must stay gated behind `signal_definition_confirmed` and must only
ever produce a proposal (never reach the broker).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.bridge.mock_bridge import MockBridge
from app.core.enums import OrderSide
from app.domain.models import Candle, StrategyPresetConfig
from app.persistence.repositories import StrategyConfigRepository
from app.strategy.proposals import ProposalService
from app.strategy.signal import SignalService, evaluate_donchian


def _c(o, h, low, c):
    return Candle(time=datetime.now(timezone.utc), open=o, high=h, low=low, close=c)


# entry_window for d40=3 is candles[-4:-1]; stop_window for d20=2 is candles[-2:]
_BUY_BREAKOUT = [
    _c(2350, 2351, 2349, 2350),
    _c(2350, 2351, 2349, 2350),
    _c(2350, 2351, 2349, 2350),
    _c(2350, 2352, 2349, 2351),
    _c(2351, 2361, 2358, 2360),  # close 2360 > 3-bar high 2352 -> BUY
]
_SELL_BREAKOUT = [
    _c(2350, 2351, 2349, 2350),
    _c(2350, 2351, 2349, 2350),
    _c(2350, 2351, 2349, 2350),
    _c(2350, 2351, 2348, 2349),
    _c(2349, 2342, 2339, 2340),  # close 2340 < 3-bar low 2348 -> SELL
]


def test_donchian_buy_breakout():
    sig = evaluate_donchian(_BUY_BREAKOUT, d40=3, d20=2)
    assert sig is not None
    assert sig.side is OrderSide.BUY
    assert sig.breakout_level == 2352
    assert sig.stop_loss == 2349  # min low of last 2 bars (2349, 2358)


def test_donchian_sell_breakout():
    sig = evaluate_donchian(_SELL_BREAKOUT, d40=3, d20=2)
    assert sig is not None
    assert sig.side is OrderSide.SELL
    assert sig.breakout_level == 2348
    assert sig.stop_loss == 2351  # max high of last 2 bars (2351, 2342)


def test_donchian_no_breakout():
    flat = [_c(2350, 2351, 2349, 2350) for _ in range(5)]
    assert evaluate_donchian(flat, d40=3, d20=2) is None


def test_donchian_insufficient_bars():
    assert evaluate_donchian(_BUY_BREAKOUT[:2], d40=3, d20=2) is None


def test_mock_candles_are_deterministic_and_sane(make_settings):
    bridge = MockBridge(settings=make_settings())
    bars = bridge.candles("XAUUSD", "H1", 50)
    assert len(bars) == 50
    assert all(b.high >= b.low for b in bars)
    # Deterministic: same args -> same series.
    assert [b.close for b in bridge.candles("XAUUSD", "H1", 50)] == [b.close for b in bars]


def _save_strategy(session, **overrides):
    cfg = StrategyPresetConfig(symbol="XAUUSD", risk_pct=1.0, **overrides)
    StrategyConfigRepository(session).save(cfg, updated_by="op")


def test_signal_disabled_when_strategy_off(order_service, make_settings):
    svc = order_service(settings=make_settings())  # default config: disabled
    result = SignalService(ProposalService(svc)).evaluate(created_by="op")
    assert result.proposal is None
    assert "disabled" in result.reason.lower()


def test_signal_gated_until_confirmed(order_service, session, make_settings):
    svc = order_service(settings=make_settings(), candles=_BUY_BREAKOUT)
    _save_strategy(session, enabled=True, d40_value=3, d20_value=2,
                   require_news_clear=False, signal_definition_confirmed=False)
    result = SignalService(ProposalService(svc)).evaluate(created_by="op")
    assert result.proposal is None
    assert "signal_definition_confirmed" in result.reason


def test_signal_generates_proposal_on_breakout(order_service, session, make_settings):
    svc = order_service(settings=make_settings(), candles=_BUY_BREAKOUT)
    _save_strategy(session, enabled=True, d40_value=3, d20_value=2,
                   require_news_clear=False, signal_definition_confirmed=True)
    result = SignalService(ProposalService(svc)).evaluate(created_by="op")
    assert result.signal is not None
    assert result.signal.side is OrderSide.BUY
    assert result.proposal is not None
    assert result.proposal.side == "BUY"


def test_signal_no_breakout_makes_no_proposal(order_service, session, make_settings):
    flat = [_c(2350, 2351, 2349, 2350) for _ in range(6)]
    svc = order_service(settings=make_settings(), candles=flat)
    _save_strategy(session, enabled=True, d40_value=3, d20_value=2,
                   require_news_clear=False, signal_definition_confirmed=True)
    result = SignalService(ProposalService(svc)).evaluate(created_by="op")
    assert result.signal is None
    assert result.proposal is None
