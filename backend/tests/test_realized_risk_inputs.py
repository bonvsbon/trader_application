"""Daily-loss and post-loss cooldown inputs from the MT5 bridge."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.enums import OrderSide, OrderState
from app.domain.models import ClosedTrade, OrderRequest


def _request(key: str) -> OrderRequest:
    return OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.1,
        sl=2349.0,
        risk_pct=1.0,
        idempotency_key=key,
    )


def test_daily_realized_loss_blocks_new_order(order_service):
    loss = ClosedTrade(
        ticket=10,
        symbol="XAUUSD",
        profit=-400.0,
        close_time=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    svc = order_service(closed_trades=[loss])
    result = svc.place_order(_request("daily-loss-block-1"))
    assert result.state is OrderState.RISK_BLOCKED
    assert any("Daily loss" in reason for reason in result.reasons)


def test_recent_losing_trade_activates_cooldown(order_service):
    loss = ClosedTrade(
        ticket=11,
        symbol="XAUUSD",
        profit=-10.0,
        close_time=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    svc = order_service(closed_trades=[loss])
    result = svc.place_order(_request("cooldown-block-12"))
    assert result.state is OrderState.RISK_BLOCKED
    assert any("Cooldown after loss" in reason for reason in result.reasons)


def test_closed_trade_feed_failure_blocks(order_service):
    svc = order_service(fail_closed_trades=True)
    result = svc.place_order(_request("closed-feed-fail"))
    assert result.state is OrderState.RISK_BLOCKED
    assert any("closed trades unavailable" in reason for reason in result.reasons)
