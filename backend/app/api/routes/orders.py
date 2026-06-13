"""Order endpoints — submit / approve / reject / recent.

Every write path delegates to OrderService; this router never touches the bridge
or risk logic directly.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import get_operator
from app.api.deps import get_order_service
from app.api.serializers import order_to_dict, pending_approval_to_dict
from app.core.enums import OrderSide
from app.domain.models import OrderRequest, OrderResult
from app.execution.idempotency import make_idempotency_key
from app.execution.order_service import OrderService
from app.persistence.repositories import RiskRepository, TradeProposalRepository

router = APIRouter(prefix="/api/orders", tags=["orders"])


class OrderTicket(BaseModel):
    symbol: str
    side: OrderSide
    volume: float = Field(gt=0)
    sl: float | None = None
    tp: float | None = None
    risk_pct: float | None = Field(default=None, gt=0)
    idempotency_key: str | None = None
    strategy_reason: str | None = None


class ApprovalBody(BaseModel):
    idempotency_key: str


@router.post("/submit", response_model=OrderResult)
def submit_order(
    ticket: OrderTicket,
    svc: OrderService = Depends(get_order_service),
    operator: str = Depends(get_operator),
) -> OrderResult:
    key = ticket.idempotency_key or make_idempotency_key(
        ticket.symbol, ticket.side.value, ticket.volume, ticket.sl, ticket.tp, bucket_seconds=2
    )
    req = OrderRequest(
        symbol=ticket.symbol,
        side=ticket.side,
        volume=ticket.volume,
        sl=ticket.sl,
        tp=ticket.tp,
        risk_pct=ticket.risk_pct,
        idempotency_key=key,
        source="manual",
        strategy_reason=ticket.strategy_reason,
        requested_by=operator,
    )
    return svc.place_order(req)


@router.post("/approve", response_model=OrderResult)
def approve_order(
    body: ApprovalBody,
    svc: OrderService = Depends(get_order_service),
    operator: str = Depends(get_operator),
) -> OrderResult:
    try:
        return svc.approve_order(body.idempotency_key, operator)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/reject", response_model=OrderResult)
def reject_order(
    body: ApprovalBody,
    svc: OrderService = Depends(get_order_service),
    operator: str = Depends(get_operator),
) -> OrderResult:
    try:
        return svc.reject_order(body.idempotency_key, operator)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/reconcile", response_model=OrderResult)
def reconcile_order(
    body: ApprovalBody,
    svc: OrderService = Depends(get_order_service),
    operator: str = Depends(get_operator),
) -> OrderResult:
    try:
        return svc.reconcile_order(body.idempotency_key, operator)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/recent")
def recent_orders(
    limit: int = 50,
    svc: OrderService = Depends(get_order_service),
    operator: str = Depends(get_operator),
) -> list[dict]:
    return [order_to_dict(o) for o in svc.orders.list_recent(limit)]


@router.get("/pending-approval")
def pending_approval_orders(
    limit: int = 50,
    svc: OrderService = Depends(get_order_service),
    operator: str = Depends(get_operator),
) -> list[dict]:
    risk = RiskRepository(svc.session, svc.mt5_account_id)
    proposals = TradeProposalRepository(svc.session, svc.mt5_account_id)
    return [
        pending_approval_to_dict(
            o,
            risk=risk.latest_for(o.idempotency_key),
            proposal=proposals.get_by_order_key(o.idempotency_key),
        )
        for o in svc.orders.list_pending_approval(limit)
    ]
