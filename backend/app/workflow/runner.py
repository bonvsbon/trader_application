"""Interval workflow runner.

The cycle syncs bridge/account/market data and reconciles previously submitted
orders. It never places a new order. Future auto execution must route through
`OrderService.place_order` like everything else.
"""

from __future__ import annotations

import asyncio

from app.ai.service import AnalysisService
from app.bridge.base import get_configured_bridge
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.ports import MT5BridgePort
from app.execution.order_service import OrderService
from app.persistence.entities import PositionRow
from app.persistence.repositories import (
    ClosedTradeRepository,
    LogRepository,
    OrderRepository,
    WorkflowRepository,
)
from app.providers.health import refresh_provider_health

logger = get_logger(__name__)

DEFAULT_SYMBOL = "XAUUSD"


class WorkflowRunner:
    def __init__(self, bridge: MT5BridgePort | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.bridge = bridge or get_configured_bridge()

    def run_once(self, session) -> dict:
        workflows = WorkflowRepository(session)
        logs = LogRepository(session)
        run = workflows.start(step="sync_mt5")
        try:
            health = self.bridge.health()
            summary: dict = {"bridge_health": health.health.value, "errors": []}
            if not health.is_healthy:
                summary["errors"].append(
                    f"bridge health is {health.health.value}: {health.detail or 'no detail'}"
                )

            try:
                account = self.bridge.account_info()
                summary.update(
                    account_type=account.account_type.value,
                    balance=account.balance,
                    equity=account.equity,
                    free_margin_pct=round(account.free_margin_pct, 1),
                )
            except Exception as exc:  # never let a sync failure crash the loop
                summary["account_error"] = str(exc)
                summary["errors"].append(f"account sync failed: {exc}")

            quote = None
            try:
                quote = self.bridge.quote(DEFAULT_SYMBOL)
                summary.update(symbol=DEFAULT_SYMBOL, bid=quote.bid, ask=quote.ask,
                               spread_points=quote.spread_points)
            except Exception as exc:
                summary["quote_error"] = str(exc)
                summary["errors"].append(f"quote sync failed: {exc}")

            try:
                positions = self.bridge.positions()
                for p in positions:
                    session.add(PositionRow(
                        ticket=p.ticket, symbol=p.symbol, side=p.side.value, volume=p.volume,
                        open_price=p.open_price, sl=p.sl, tp=p.tp, profit=p.profit,
                        open_time=p.open_time,
                    ))
                summary["open_positions"] = len(positions)
            except Exception as exc:
                summary["positions_error"] = str(exc)
                summary["errors"].append(f"positions sync failed: {exc}")

            try:
                closed = self.bridge.closed_trades_today()
                order_by_ticket = {
                    o.order_ticket: o
                    for o in OrderRepository(session).list_filled_with_ticket()
                    if o.order_ticket is not None
                }
                summary["closed_trades_synced"] = ClosedTradeRepository(
                    session
                ).upsert_from_bridge(closed, order_by_ticket)
            except Exception as exc:
                summary["closed_trades_error"] = str(exc)
                summary["errors"].append(f"closed trades sync failed: {exc}")

            reconciled: list[dict] = []
            order_service = OrderService(session, self.bridge, settings=self.settings)
            expired_approvals = order_service.expire_pending_approvals()
            pending_orders = OrderRepository(session).list_reconciliation_pending(
                limit=self.settings.reconciliation_batch_size
            )
            reconciliation_alerts = 0
            for order in pending_orders:
                result = order_service.reconcile_order(
                    order.idempotency_key,
                    reconciled_by="workflow",
                )
                if result.state.value in {"SUBMITTED", "RECONCILIATION_REQUIRED"}:
                    reconciliation_alerts += int(
                        order_service.alert_expired_reconciliation(order)
                    )
                reconciled.append({
                    "idempotency_key": order.idempotency_key,
                    "state": result.state.value,
                    "message": result.message,
                })
            summary["reconciliation"] = {
                "checked": len(pending_orders),
                "expired_alerts": reconciliation_alerts,
                "results": reconciled,
            }
            summary["expired_approvals"] = len(expired_approvals)

            try:
                summary["provider_health"] = asyncio.run(
                    refresh_provider_health(session, self.settings)
                )
            except Exception as exc:
                summary["provider_health"] = {
                    "periodic_enabled": (
                        self.settings.analysis_provider_health_checks_enabled
                    ),
                    "checked": 0,
                    "error": (str(exc) or type(exc).__name__)[:2000],
                }

            if self.settings.workflow_analysis_enabled:
                analysis = AnalysisService(session, self.settings).analyze(
                    "chart_market",
                    (
                        "Summarize the current market snapshot for monitoring only. "
                        "Do not recommend or place an order."
                    ),
                    {
                        "symbol": DEFAULT_SYMBOL,
                        "quote": quote.model_dump(mode="json") if quote else None,
                        "bridge_health": health.health.value,
                        "open_positions": summary.get("open_positions"),
                    },
                )
                summary["analysis"] = {
                    "available": analysis.available,
                    "summary": analysis.summary,
                    "provider": analysis.provider_name,
                    "model_or_tool": analysis.model_or_tool,
                    "correlation_id": analysis.correlation_id,
                }

            status = "partial" if summary["errors"] else "ok"
            workflows.finish(run, status=status, step="done", detail=summary)
            logs.add(
                "WARNING" if summary["errors"] else "INFO",
                "workflow",
                "Workflow cycle completed with errors"
                if summary["errors"]
                else "Workflow cycle complete",
                summary,
            )
            return summary
        except Exception as exc:
            logger.exception("Workflow cycle failed")
            workflows.finish(run, status="error", step="sync_mt5", error=str(exc))
            logs.add("ERROR", "workflow", "Workflow cycle failed", {"error": str(exc)})
            raise
