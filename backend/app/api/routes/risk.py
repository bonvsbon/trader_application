"""Risk Monitor — live ALLOW/WARN/BLOCK state and the facts behind it."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_order_service
from app.core.enums import OrderSide
from app.domain.models import OrderRequest
from app.execution.idempotency import make_idempotency_key
from app.execution.order_service import OrderService

router = APIRouter(prefix="/api/risk", tags=["risk"])


class OrderRiskPreview(BaseModel):
    symbol: str
    side: OrderSide
    volume: float = Field(gt=0)
    sl: float | None = None
    tp: float | None = None
    risk_pct: float | None = Field(default=None, gt=0)


def _preview_response(result, ctx, svc: OrderService) -> dict:
    entry_price = None
    if ctx.quote is not None:
        entry_price = ctx.quote.ask if ctx.request.side is OrderSide.BUY else ctx.quote.bid
    return {
        "decision": result.decision.value,
        "reasons": result.reasons,
        "warnings": result.warnings,
        "sizing": {
            "entry_price": entry_price,
            "estimated_loss": ctx.estimated_loss,
            "estimated_reward": ctx.estimated_reward,
            "sized_risk_pct": ctx.sized_risk_pct,
            "max_volume_for_risk": ctx.max_volume_for_risk,
            "current_portfolio_risk_pct": ctx.current_portfolio_risk_pct,
            "projected_portfolio_risk_pct": (
                ctx.current_portfolio_risk_pct + ctx.sized_risk_pct
                if ctx.current_portfolio_risk_pct is not None
                and ctx.sized_risk_pct is not None
                else None
            ),
        },
        "limits": {
            "max_risk_per_trade_pct": svc.settings.risk_max_risk_per_trade_pct,
            "max_portfolio_risk_pct": svc.settings.risk_max_portfolio_risk_pct,
            "max_order_volume_lots": svc.settings.risk_max_order_volume_lots,
        },
    }


@router.post("/preview")
def preview_order(
    ticket: OrderRiskPreview,
    svc: OrderService = Depends(get_order_service),
) -> dict:
    req = OrderRequest(
        symbol=ticket.symbol,
        side=ticket.side,
        volume=ticket.volume,
        sl=ticket.sl,
        tp=ticket.tp,
        risk_pct=ticket.risk_pct,
        idempotency_key=make_idempotency_key(
            "preview",
            ticket.symbol,
            ticket.side.value,
            ticket.volume,
            ticket.sl,
            ticket.tp,
            ticket.risk_pct,
        ),
        source="manual",
        requested_by="order-preview",
    )
    result, ctx = svc.preview(req)
    return _preview_response(result, ctx, svc)


@router.get("/status")
def risk_status(
    symbol: str = "XAUUSD",
    side: OrderSide = OrderSide.BUY,
    volume: float = 0.1,
    risk_pct: float | None = None,
    svc: OrderService = Depends(get_order_service),
) -> dict:
    req = OrderRequest(
        symbol=symbol,
        side=side,
        volume=volume,
        risk_pct=risk_pct or svc.settings.risk_max_risk_per_trade_pct,
        idempotency_key=make_idempotency_key("probe", symbol, side.value, volume),
        source="probe",
        requested_by="risk-monitor",
    )
    result, ctx = svc.preview(req)
    return {
        "decision": result.decision.value,
        "reasons": result.reasons,
        "warnings": result.warnings,
        "facts": {
            "bridge_health": ctx.bridge_health.value,
            "account_type": ctx.account.account_type.value,
            "free_margin_pct": round(ctx.account.free_margin_pct, 1),
            "spread_points": ctx.quote.spread_points if ctx.quote else None,
            "open_positions": ctx.open_positions,
            "trades_today": ctx.trades_today,
            "abnormal_volatility": ctx.abnormal_volatility,
            "news_high_impact": ctx.news.has_high_impact_within_window,
            "news_provider": ctx.news.provider,
            "news_is_live": ctx.news.is_live,
            "volatility_provider": ctx.volatility.provider,
            "volatility_is_live": ctx.volatility.is_live,
            "config_problems": ctx.config_problems,
            "data_problems": ctx.data_problems,
        },
        "limits": {
            "max_risk_per_trade_pct": svc.settings.risk_max_risk_per_trade_pct,
            "max_open_positions": svc.settings.risk_max_open_positions,
            "max_trades_per_day": svc.settings.risk_max_trades_per_day,
            "max_spread_points": svc.settings.risk_max_spread_points,
            "daily_max_loss_pct": svc.settings.risk_daily_max_loss_pct,
            "max_order_volume_lots": svc.settings.risk_max_order_volume_lots,
        },
    }
