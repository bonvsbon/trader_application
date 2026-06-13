"""Interval workflow runner.

The cycle syncs bridge/account/market data and reconciles previously submitted
orders. Optional auto-demo execution remains separately gated and always routes
through ProposalService -> OrderService -> Risk Engine.
"""

from __future__ import annotations

import asyncio

from app.ai.service import AnalysisService
from app.bridge.base import get_configured_bridge
from app.core.config import Settings, get_settings
from app.core.enums import AccountType, TradingMode
from app.core.logging import get_logger
from app.domain.ports import MT5BridgePort
from app.execution.order_service import OrderService
from app.news.base import create_news_provider
from app.persistence.entities import PositionRow
from app.persistence.repositories import (
    ClosedTradeRepository,
    LogRepository,
    OrderRepository,
    WorkflowRepository,
)
from app.providers.health import refresh_provider_health
from app.strategy.proposals import ProposalService
from app.strategy.signal import SignalService
from app.volatility.base import create_volatility_provider

logger = get_logger(__name__)

DEFAULT_SYMBOL = "XAUUSD"


class WorkflowRunner:
    def __init__(self, bridge: MT5BridgePort | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.bridge = bridge or get_configured_bridge()

    def run_once(self, session, mt5_account_id: int = 1) -> dict:
        workflows = WorkflowRepository(session, mt5_account_id)
        logs = LogRepository(session)
        run = workflows.start(step="sync_mt5")
        try:
            health = self.bridge.health()
            summary: dict = {"bridge_health": health.health.value, "errors": []}
            if not health.is_healthy:
                summary["errors"].append(
                    f"bridge health is {health.health.value}: {health.detail or 'no detail'}"
                )

            account = None
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
                        mt5_account_id=mt5_account_id,
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
                    for o in OrderRepository(
                        session, mt5_account_id
                    ).list_filled_with_ticket()
                    if o.order_ticket is not None
                }
                summary["closed_trades_synced"] = ClosedTradeRepository(
                    session, mt5_account_id
                ).upsert_from_bridge(closed, order_by_ticket)
            except Exception as exc:
                summary["closed_trades_error"] = str(exc)
                summary["errors"].append(f"closed trades sync failed: {exc}")

            reconciled: list[dict] = []
            order_service = OrderService(
                session,
                self.bridge,
                settings=self.settings,
                news_provider=create_news_provider(
                    self.settings,
                    session,
                    mt5_account_id=mt5_account_id,
                ),
                volatility_provider=create_volatility_provider(
                    self.settings,
                    self.bridge,
                ),
                mt5_account_id=mt5_account_id,
            )
            expired_approvals = order_service.expire_pending_approvals()
            pending_orders = OrderRepository(
                session, mt5_account_id
            ).list_reconciliation_pending(
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
                analysis = AnalysisService(
                    session,
                    self.settings,
                    mt5_account_id=mt5_account_id,
                ).analyze(
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

            summary["auto_demo"] = self._run_auto_demo(
                order_service,
                account_type=account.account_type if account else AccountType.UNKNOWN,
            )

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

    def _run_auto_demo(
        self,
        order_service: OrderService,
        *,
        account_type: AccountType,
    ) -> dict:
        if not self.settings.workflow_auto_demo_enabled:
            return {"status": "disabled"}
        if self.settings.trading_mode is not TradingMode.AUTO_DEMO:
            return {
                "status": "blocked",
                "reason": "TRADING_MODE is not AUTO_DEMO",
            }
        if account_type is not AccountType.DEMO:
            return {
                "status": "blocked",
                "reason": f"Connected account is {account_type.value}, not DEMO",
            }

        proposals = ProposalService(order_service)
        signal = SignalService(proposals).evaluate(created_by="workflow-auto-demo")
        if signal.proposal is None:
            return {"status": "no_signal", "reason": signal.reason}
        proposal = signal.proposal
        if proposal.status != "DRAFT":
            return {
                "status": "already_processed",
                "reason": signal.reason,
                "proposal_id": proposal.id,
                "proposal_status": proposal.status,
            }

        result = proposals.submit(
            proposal.id,
            submitted_by="workflow-auto-demo",
            source="auto",
        )
        return {
            "status": "submitted",
            "reason": signal.reason,
            "proposal_id": proposal.id,
            "order_id": result.order_id,
            "order_state": result.state.value,
            "risk_decision": result.decision.value,
            "idempotency_key": result.idempotency_key,
        }
