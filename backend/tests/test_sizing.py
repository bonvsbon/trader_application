"""Position sizing and protection-price calculations."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.enums import AccountType, OrderSide
from app.domain.models import AccountInfo, OrderRequest, SymbolInfo, SymbolQuote
from app.risk.sizing import calculate_position_sizing, price_directions_valid


def _quote() -> SymbolQuote:
    return SymbolQuote(
        symbol="XAUUSD",
        bid=2349.9,
        ask=2350.1,
        spread_points=20,
        time=datetime.now(timezone.utc),
    )


def _info() -> SymbolInfo:
    return SymbolInfo(
        symbol="XAUUSD",
        tick_size=0.01,
        tick_value=1.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )


def test_buy_position_sizing_uses_equity_stop_distance_and_tick_value():
    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.5,
        sl=2349.1,
        tp=2352.1,
        risk_pct=1.0,
        idempotency_key="sizing-buy-1234",
    )
    account = AccountInfo(
        account_type=AccountType.DEMO,
        equity=10_000,
        free_margin=10_000,
    )
    sizing = calculate_position_sizing(request, _quote(), _info(), account)
    assert sizing is not None
    assert sizing.estimated_loss == 50.0
    assert sizing.estimated_reward == 100.0
    assert sizing.sized_risk_pct == 0.5
    assert sizing.max_volume_for_risk == 1.0


def test_invalid_buy_protection_prices_are_reported():
    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.1,
        sl=2351.0,
        tp=2349.0,
        risk_pct=1.0,
        idempotency_key="sizing-price-12",
    )
    problems = price_directions_valid(request, 2350.1)
    assert len(problems) == 2
    assert any("stop loss" in problem for problem in problems)
    assert any("take profit" in problem for problem in problems)
