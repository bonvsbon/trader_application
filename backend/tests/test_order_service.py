"""Order chokepoint tests — the core safety guarantees.

These assert behaviour, not implementation: demo ALLOW fills with an audit log;
unknown account / unhealthy bridge block; real accounts queue for approval;
duplicates never place a second order; bridge failures end in ERROR (never a
silent gap).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.enums import AccountType, BridgeHealth, OrderSide, OrderState, RiskDecision
from app.domain.models import OrderRequest
from app.news.base import MockNewsProvider
from app.persistence.repositories import AuditRepository, OrderRepository
from app.volatility.base import MockVolatilityProvider


def _req(key: str = "order-key-123456", **overrides) -> OrderRequest:
    base = dict(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.1,
        sl=2349.0,
        risk_pct=1.0,
        idempotency_key=key,
        source="manual",
    )
    base.update(overrides)
    return OrderRequest(**base)


def test_demo_allow_fills_with_audit(order_service, session):
    svc = order_service()  # mock bridge: healthy + demo
    result = svc.place_order(_req())
    assert result.state is OrderState.FILLED
    assert result.decision is RiskDecision.ALLOW
    assert result.mt5_response and result.mt5_response["ticket"]

    events = [a.event for a in AuditRepository(session).list_recent()]
    assert "order.filled" in events


def test_unknown_account_blocks(order_service):
    svc = order_service(account_type=AccountType.UNKNOWN)
    result = svc.place_order(_req())
    assert result.state is OrderState.RISK_BLOCKED
    assert result.decision is RiskDecision.BLOCK
    assert result.mt5_response is None


def test_unhealthy_bridge_blocks(order_service):
    svc = order_service(health=BridgeHealth.UNHEALTHY)
    result = svc.place_order(_req())
    assert result.state is OrderState.RISK_BLOCKED


def test_real_account_requires_approval_then_fills(order_service, make_settings):
    settings = make_settings(
        allow_real_trading=True,
        api_auth_required=True,
        api_auth_token="test-token",
    )
    svc = order_service(settings=settings, account_type=AccountType.REAL)
    pending = svc.place_order(_req())
    assert pending.state is OrderState.PENDING_APPROVAL
    assert pending.mt5_response is None  # not executed yet

    filled = svc.approve_order(pending.idempotency_key, approved_by="tester")
    assert filled.state is OrderState.FILLED
    assert filled.mt5_response and filled.mt5_response["ticket"]

    approved = next(
        event for event in AuditRepository(svc.session).list_recent()
        if event.event == "order.approved"
    )
    assert approved.payload == {"approved_by": "tester"}


def test_real_account_blocks_when_live_news_and_volatility_are_unavailable(
    order_service,
    make_settings,
):
    settings = make_settings(
        allow_real_trading=True,
        api_auth_required=True,
        api_auth_token="test-token",
    )
    svc = order_service(
        settings=settings,
        account_type=AccountType.REAL,
        news_provider=MockNewsProvider(),
        volatility_provider=MockVolatilityProvider(),
    )

    result = svc.place_order(_req(key="real-provider-gate-123"))

    assert result.state is OrderState.RISK_BLOCKED
    assert any("news data unavailable" in reason for reason in result.reasons)
    assert any("volatility/session data unavailable" in reason for reason in result.reasons)


def test_configured_live_volatility_provider_blocks_demo_when_data_is_stale(
    order_service,
    make_settings,
):
    settings = make_settings(volatility_provider="mt5")
    svc = order_service(
        settings=settings,
        volatility_provider=MockVolatilityProvider(),
    )

    result = svc.place_order(_req(key="demo-stale-volatility-123"))

    assert result.state is OrderState.RISK_BLOCKED
    assert any(
        "Live volatility/session data unavailable" in reason
        for reason in result.reasons
    )


def test_expired_approval_is_cancelled_without_execution(
    order_service,
    make_settings,
):
    settings = make_settings(
        allow_real_trading=True,
        api_auth_required=True,
        api_auth_token="test-token",
        approval_expiry_minutes=5,
    )
    svc = order_service(settings=settings, account_type=AccountType.REAL)
    pending = svc.place_order(_req(key="expired-approval-123"))
    row = svc.orders.get_by_key(pending.idempotency_key)
    row.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    svc.session.flush()

    expired = svc.approve_order(pending.idempotency_key, approved_by="tester")

    assert expired.state is OrderState.CANCELLED
    assert "expired" in expired.message.lower()
    assert expired.mt5_response is None
    events = [event.event for event in AuditRepository(svc.session).list_recent()]
    assert "order.approval_expired" in events


def test_real_account_blocked_when_real_trading_disabled(order_service, make_settings):
    svc = order_service(settings=make_settings(allow_real_trading=False), account_type=AccountType.REAL)
    result = svc.place_order(_req())
    assert result.state is OrderState.RISK_BLOCKED
    assert any("Real-account trading is disabled" in r for r in result.reasons)


def test_duplicate_key_returns_prior_result(order_service, session):
    svc = order_service()
    first = svc.place_order(_req(key="dup-key-12345678"))
    second = svc.place_order(_req(key="dup-key-12345678"))
    assert first.order_id == second.order_id
    assert "Duplicate" in second.message
    assert len(OrderRepository(session).list_recent()) == 1  # no second order row


def test_suspected_duplicate_blocks(order_service):
    svc = order_service()
    first = svc.place_order(_req(key="first-key-1234567", volume=0.2))
    assert first.state is OrderState.FILLED
    second = svc.place_order(_req(key="second-key-123456", volume=0.2))
    assert second.state is OrderState.RISK_BLOCKED
    assert any("Suspected duplicate" in r for r in second.reasons)


def test_bridge_failure_requires_reconciliation(order_service):
    svc = order_service(fail_execute=True)
    result = svc.place_order(_req())
    assert result.state is OrderState.RECONCILIATION_REQUIRED


def test_broker_rejection_is_not_marked_filled(order_service, session):
    svc = order_service(
        execute_response={"retcode": 10006, "retcode_text": "Request rejected"}
    )
    result = svc.place_order(_req(key="broker-reject-1234"))
    assert result.state is OrderState.REJECTED
    assert result.message == "Request rejected"
    events = [a.event for a in AuditRepository(session).list_recent()]
    assert "order.broker_rejected" in events
    assert "order.filled" not in events


def test_malformed_success_response_requires_reconciliation(order_service):
    svc = order_service(execute_response={"retcode": 10009, "retcode_text": "Done"})
    result = svc.place_order(_req(key="missing-ticket-1234"))
    assert result.state is OrderState.RECONCILIATION_REQUIRED
    assert "ticket" in result.message


def test_broker_accepted_order_stays_submitted(order_service):
    svc = order_service(
        execute_response={"retcode": 10008, "retcode_text": "Order placed", "ticket": 42}
    )
    result = svc.place_order(_req(key="broker-placed-1234"))
    assert result.state is OrderState.SUBMITTED
    assert "awaiting reconciliation" in result.message


def test_broker_accepted_response_without_ticket_results_in_error(order_service):
    svc = order_service(execute_response={"retcode": 10008, "retcode_text": "Order placed"})
    result = svc.place_order(_req(key="placed-no-ticket-1"))
    assert result.state is OrderState.RECONCILIATION_REQUIRED
    assert "valid order ticket" in result.message


def test_uncertain_order_can_be_reconciled_to_filled(order_service):
    svc = order_service(
        fail_execute=True,
        order_status_response={
            "retcode": 10009,
            "retcode_text": "Request completed",
            "ticket": 99,
        },
    )
    uncertain = svc.place_order(_req(key="reconcile-fill-123"))
    assert uncertain.state is OrderState.RECONCILIATION_REQUIRED
    filled = svc.reconcile_order(uncertain.idempotency_key, "tester")
    assert filled.state is OrderState.FILLED
    assert filled.mt5_response and filled.mt5_response["ticket"] == 99


def test_quote_failure_blocks_before_execution(order_service):
    svc = order_service(fail_quote=True)
    result = svc.place_order(_req(key="quote-fail-12345"))
    assert result.state is OrderState.RISK_BLOCKED
    assert any("quote unavailable" in reason for reason in result.reasons)


def test_positions_failure_blocks_before_execution(order_service):
    svc = order_service(fail_positions=True)
    result = svc.place_order(_req(key="positions-fail-12"))
    assert result.state is OrderState.RISK_BLOCKED
    assert any("open positions unavailable" in reason for reason in result.reasons)


def test_stale_heartbeat_blocks(order_service, make_settings):
    settings = make_settings(mt5_heartbeat_max_age_sec=5)
    svc = order_service(settings=settings, heartbeat_age_seconds=30)
    result = svc.place_order(_req(key="stale-heartbeat-1"))
    assert result.state is OrderState.RISK_BLOCKED
    assert any("bridge is not healthy" in reason.lower() for reason in result.reasons)


def test_default_mode_disables_auto_real_full(make_settings):
    # Safety: the default config must never enable fully-automatic real trading.
    assert make_settings().auto_real_full_enabled() is False
