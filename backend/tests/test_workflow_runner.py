from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.bridge.mock_bridge import MockBridge
from app.core.enums import OrderSide, OrderState, TradingMode
from app.domain.models import Candle, OrderRequest, StrategyPresetConfig
from app.execution.order_service import OrderService
from app.persistence.entities import AnalysisProviderRow
from app.persistence.repositories import (
    AuditRepository,
    LogRepository,
    OrderRepository,
    StrategyConfigRepository,
    TradeProposalRepository,
)
from app.workflow.runner import WorkflowRunner


def test_workflow_reconciles_uncertain_order(session, make_settings):
    settings = make_settings()
    bridge = MockBridge(
        settings=settings,
        fail_execute=True,
        order_status_response={
            "retcode": 10009,
            "retcode_text": "Request completed",
            "ticket": 7_654_321,
        },
    )
    service = OrderService(session, bridge, settings=settings)
    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.1,
        sl=2349.0,
        tp=2352.0,
        risk_pct=1.0,
        idempotency_key="workflow-reconcile-1234",
    )

    uncertain = service.place_order(request)
    assert uncertain.state is OrderState.RECONCILIATION_REQUIRED

    summary = WorkflowRunner(bridge=bridge, settings=settings).run_once(session)

    assert summary["reconciliation"]["checked"] == 1
    assert summary["reconciliation"]["results"][0]["state"] == OrderState.FILLED.value
    assert service.orders.get_by_key(request.idempotency_key).state == OrderState.FILLED.value


def test_workflow_alerts_once_when_reconciliation_expires(session, make_settings):
    settings = make_settings(reconciliation_expiry_minutes=5)
    bridge = MockBridge(settings=settings, fail_execute=True)
    service = OrderService(session, bridge, settings=settings)
    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.1,
        sl=2349.0,
        risk_pct=1.0,
        idempotency_key="expired-reconcile-123",
    )
    uncertain = service.place_order(request)
    row = service.orders.get_by_key(uncertain.idempotency_key)
    row.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    session.flush()
    runner = WorkflowRunner(bridge=bridge, settings=settings)

    first = runner.run_once(session)
    second = runner.run_once(session)

    assert first["reconciliation"]["expired_alerts"] == 1
    assert second["reconciliation"]["expired_alerts"] == 0
    events = [
        event
        for event in AuditRepository(session).list_recent()
        if event.event == "order.reconciliation_expired"
    ]
    logs = [
        log
        for log in LogRepository(session).list_recent()
        if log.source == "reconciliation" and log.level == "ERROR"
    ]
    assert len(events) == 1
    assert len(logs) == 1


def test_workflow_reports_partial_bridge_sync_failures(session, make_settings):
    settings = make_settings()
    bridge = MockBridge(
        settings=settings,
        fail_quote=True,
        fail_positions=True,
        fail_closed_trades=True,
    )

    summary = WorkflowRunner(bridge=bridge, settings=settings).run_once(session)

    assert len(summary["errors"]) == 3
    assert "quote_error" in summary
    assert "positions_error" in summary
    assert "closed_trades_error" in summary
    workflow_logs = [
        log for log in LogRepository(session).list_recent()
        if log.source == "workflow"
    ]
    assert workflow_logs[0].level == "WARNING"


def test_workflow_provider_health_failure_is_advisory(
    session,
    make_settings,
    monkeypatch,
):
    settings = make_settings()
    bridge = MockBridge(settings=settings)

    async def fake_refresh(session, settings):
        raise RuntimeError("provider monitor unavailable")

    monkeypatch.setattr(
        "app.workflow.runner.refresh_provider_health",
        fake_refresh,
    )

    summary = WorkflowRunner(bridge=bridge, settings=settings).run_once(session)

    assert summary["errors"] == []
    assert summary["provider_health"]["checked"] == 0
    assert summary["provider_health"]["error"] == "provider monitor unavailable"


def test_auto_demo_submits_once_per_closed_signal_bar(
    session,
    make_settings,
    monkeypatch,
):
    settings = make_settings(
        trading_mode=TradingMode.AUTO_DEMO,
        workflow_auto_demo_enabled=True,
        strategy_timeframe="H1",
    )
    closed_at = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
    candles = [
        Candle(time=closed_at - timedelta(hours=4), open=2350, high=2351, low=2349, close=2350),
        Candle(time=closed_at - timedelta(hours=3), open=2350, high=2351, low=2349, close=2350),
        Candle(time=closed_at - timedelta(hours=2), open=2350, high=2351, low=2349, close=2350),
        Candle(time=closed_at - timedelta(hours=1), open=2350, high=2352, low=2349, close=2351),
        Candle(time=closed_at, open=2351, high=2361, low=2358, close=2360),
    ]
    bridge = MockBridge(settings=settings, candles=candles)
    StrategyConfigRepository(session).save(
        StrategyPresetConfig(
            enabled=True,
            d40_value=3,
            d20_value=2,
            require_news_clear=False,
            signal_definition_confirmed=True,
        ),
        updated_by="tester",
    )
    session.add(
        AnalysisProviderRow(
            display_name="Workflow advisory",
            provider_type="local",
            enabled=True,
            endpoint="http://127.0.0.1:3000",
            model_name="test-model",
            timeout_sec=5,
            priority=1,
            capabilities=["proposal_explanation"],
            allowed_tools=[],
            capability_tools={},
            health="HEALTHY",
        )
    )
    session.flush()

    async def skip_health_refresh(session, settings):
        return {"checked": 0, "healthy": 0, "unhealthy": 0}

    monkeypatch.setattr(
        "app.workflow.runner.refresh_provider_health",
        skip_health_refresh,
    )
    monkeypatch.setattr(
        "app.ai.service.OpenWebUIProvider.analyze",
        lambda self, prompt, context: {
            "summary": "Deterministic strategy advisory context",
            "confidence": 0.5,
        },
    )
    runner = WorkflowRunner(bridge=bridge, settings=settings)

    first = runner.run_once(session)
    second = runner.run_once(session)

    assert first["auto_demo"]["status"] == "submitted"
    assert first["auto_demo"]["order_state"] == OrderState.FILLED.value
    assert second["auto_demo"]["status"] == "already_processed"
    assert len(OrderRepository(session).list_recent()) == 1
    assert len(TradeProposalRepository(session).list_recent()) == 1
