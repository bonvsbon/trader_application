"""Dashboard aggregate — one call for the overview page."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_order_service
from app.core.enums import OrderSide
from app.domain.models import OrderRequest
from app.execution.idempotency import make_idempotency_key
from app.execution.order_service import OrderService
from app.news.base import upcoming_news_events
from app.workflow.scheduler import get_scheduler

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(svc: OrderService = Depends(get_order_service)) -> dict:
    s = svc.settings
    req = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.1,
        risk_pct=s.risk_max_risk_per_trade_pct,
        idempotency_key=make_idempotency_key("dashboard", "XAUUSD"),
        source="probe",
        requested_by="dashboard",
    )
    risk, ctx = svc.preview(req)
    return {
        "trading_mode": s.trading_mode.value,
        "bridge_health": ctx.bridge_health.value,
        "account": {
            "account_type": ctx.account.account_type.value,
            "balance": ctx.account.balance,
            "equity": ctx.account.equity,
            "free_margin_pct": round(ctx.account.free_margin_pct, 1),
        },
        "quote": (
            {"symbol": ctx.quote.symbol, "bid": ctx.quote.bid, "ask": ctx.quote.ask,
             "spread_points": ctx.quote.spread_points}
            if ctx.quote else None
        ),
        "open_positions": ctx.open_positions,
        "trades_today": ctx.trades_today,
        "news": {
            "high_impact": ctx.news.has_high_impact_within_window,
            "summary": ctx.news.summary,
            "provider": ctx.news.provider,
            "is_live": ctx.news.is_live,
            "events": upcoming_news_events(
                svc.news_provider,
                req.symbol,
            ),
        },
        "volatility": {
            "abnormal": ctx.volatility.abnormal,
            "summary": ctx.volatility.summary,
            "provider": ctx.volatility.provider,
            "is_live": ctx.volatility.is_live,
        },
        "risk": {
            "decision": risk.decision.value,
            "reasons": risk.reasons,
            "warnings": risk.warnings,
        },
        "safety_flags": {
            "allow_real_trading": s.allow_real_trading,
            "allow_auto_real_full": s.allow_auto_real_full,
            "emergency_stop": s.emergency_stop,
            "auto_real_full_enabled": s.auto_real_full_enabled(),
        },
        "workflow": get_scheduler().status(),
    }
