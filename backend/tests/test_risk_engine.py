"""Risk Engine unit tests — every hard BLOCK condition + the clean ALLOW path."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.enums import AccountType, BridgeHealth, OrderSide, RiskDecision, TradingMode
from app.domain.models import (
    AccountInfo,
    NewsRisk,
    OrderRequest,
    RiskContext,
    SymbolInfo,
    SymbolQuote,
)
from app.risk.engine import RiskEngine


def _ctx(**overrides) -> RiskContext:
    base = dict(
        request=OrderRequest(
            symbol="XAUUSD",
            side=OrderSide.BUY,
            volume=0.1,
            sl=2349.0,
            risk_pct=1.0,
            idempotency_key="risk-key-123456",
        ),
        trading_mode=TradingMode.MANUAL_ONLY,
        account=AccountInfo(account_type=AccountType.DEMO, equity=10_000, free_margin=10_000),
        bridge_health=BridgeHealth.HEALTHY,
        quote=SymbolQuote(
            symbol="XAUUSD",
            bid=2349.9,
            ask=2350.1,
            spread_points=20,
            time=datetime.now(timezone.utc),
        ),
        symbol_info=SymbolInfo(
            symbol="XAUUSD",
            tick_size=0.01,
            tick_value=1.0,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
        ),
        estimated_loss=11.0,
        estimated_reward=None,
        sized_risk_pct=0.11,
        max_volume_for_risk=0.9,
        current_portfolio_risk_pct=0.0,
    )
    base.update(overrides)
    return RiskContext(**base)


def test_allow_when_clean(make_settings):
    result = RiskEngine(make_settings()).evaluate(_ctx())
    assert result.decision is RiskDecision.ALLOW


def test_readiness_probe_does_not_require_order_prices(make_settings):
    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.1,
        risk_pct=1.0,
        idempotency_key="readiness-probe-1234",
        source="probe",
    )
    result = RiskEngine(make_settings()).evaluate(
        _ctx(
            request=request,
            estimated_loss=None,
            estimated_reward=None,
            sized_risk_pct=None,
            max_volume_for_risk=None,
        )
    )
    assert result.decision is RiskDecision.ALLOW


def test_unknown_account_blocks(make_settings):
    result = RiskEngine(make_settings()).evaluate(
        _ctx(account=AccountInfo(account_type=AccountType.UNKNOWN))
    )
    assert result.decision is RiskDecision.BLOCK
    assert any("Account type is unknown" in r for r in result.reasons)


def test_unhealthy_bridge_blocks(make_settings):
    result = RiskEngine(make_settings()).evaluate(_ctx(bridge_health=BridgeHealth.UNKNOWN))
    assert result.decision is RiskDecision.BLOCK


def test_high_impact_news_blocks(make_settings):
    result = RiskEngine(make_settings()).evaluate(
        _ctx(news=NewsRisk(has_high_impact_within_window=True, summary="NFP"))
    )
    assert result.decision is RiskDecision.BLOCK


def test_wide_spread_blocks(make_settings):
    quote = SymbolQuote(
        symbol="XAUUSD", bid=2350, ask=2351, spread_points=40, time=datetime.now(timezone.utc)
    )
    result = RiskEngine(make_settings(risk_max_spread_points=10)).evaluate(_ctx(quote=quote))
    assert result.decision is RiskDecision.BLOCK


def test_emergency_stop_blocks(make_settings):
    result = RiskEngine(make_settings(emergency_stop=True)).evaluate(_ctx())
    assert result.decision is RiskDecision.BLOCK


def test_real_account_blocked_when_disabled(make_settings):
    result = RiskEngine(make_settings(allow_real_trading=False)).evaluate(
        _ctx(account=AccountInfo(account_type=AccountType.REAL, equity=10_000, free_margin=10_000))
    )
    assert result.decision is RiskDecision.BLOCK
    assert any("Real-account trading is disabled" in r for r in result.reasons)


def test_excess_risk_per_trade_blocks(make_settings):
    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.1,
        sl=2349.0,
        idempotency_key="risk-key-654321",
        risk_pct=5.0,
    )
    result = RiskEngine(make_settings(risk_max_risk_per_trade_pct=1.0)).evaluate(_ctx(request=request))
    assert result.decision is RiskDecision.BLOCK


def test_missing_risk_percentage_blocks(make_settings):
    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.1,
        sl=2349.0,
        idempotency_key="missing-risk-1234",
    )
    result = RiskEngine(make_settings()).evaluate(_ctx(request=request))
    assert result.decision is RiskDecision.BLOCK
    assert any("Risk percentage is required" in r for r in result.reasons)


def test_excess_order_volume_blocks(make_settings):
    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=2.0,
        sl=2349.0,
        risk_pct=1.0,
        idempotency_key="large-volume-123",
    )
    result = RiskEngine(make_settings(risk_max_order_volume_lots=1.0)).evaluate(
        _ctx(request=request)
    )
    assert result.decision is RiskDecision.BLOCK
    assert any("exceeds safety limit" in r for r in result.reasons)


def test_non_positive_equity_blocks(make_settings):
    account = AccountInfo(account_type=AccountType.DEMO, equity=0, free_margin=0)
    result = RiskEngine(make_settings()).evaluate(_ctx(account=account))
    assert result.decision is RiskDecision.BLOCK
    assert any("equity" in r.lower() for r in result.reasons)


def test_missing_required_risk_data_blocks(make_settings):
    result = RiskEngine(make_settings()).evaluate(
        _ctx(data_problems=["quote unavailable for XAUUSD"])
    )
    assert result.decision is RiskDecision.BLOCK
    assert any("Risk data unavailable" in r for r in result.reasons)


def test_auto_order_is_blocked_in_manual_mode_without_reasons(make_settings):
    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.1,
        sl=2349.0,
        risk_pct=1.0,
        idempotency_key="auto-guard-12345",
        source="auto",
    )
    result = RiskEngine(make_settings()).evaluate(_ctx(request=request))
    assert result.decision is RiskDecision.BLOCK
    assert any("MANUAL_ONLY" in r for r in result.reasons)
    assert any("strategy reason" in r for r in result.reasons)
    assert any("AI reason" in r for r in result.reasons)
