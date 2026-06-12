"""Trade history — closed trades with realized P&L and R-multiple."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.service import AnalysisService
from app.api.auth import get_operator
from app.api.routes.analysis import analysis_result_to_dict
from app.api.serializers import closed_trade_to_dict
from app.bridge.base import get_configured_bridge
from app.core.logging import get_logger
from app.persistence.db import get_db
from app.persistence.repositories import ClosedTradeRepository, OrderRepository

logger = get_logger(__name__)

router = APIRouter(prefix="/api/history", tags=["history"])


class TradeReview(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


@router.get("/trades")
def history_trades(
    limit: int = 100,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> list[dict]:
    return [closed_trade_to_dict(t) for t in ClosedTradeRepository(session).list_recent(limit)]


@router.get("/summary")
def history_summary(
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> dict:
    return ClosedTradeRepository(session).summary()


@router.get("/daily")
def history_daily(
    limit_days: int = 30,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> list[dict]:
    return ClosedTradeRepository(session).daily_breakdown(limit_days)


@router.get("/review")
def history_review_queue(
    only_unreviewed: bool = False,
    limit: int = 100,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> list[dict]:
    """Losing closed trades — the post-trade review journal."""
    return [
        closed_trade_to_dict(t)
        for t in ClosedTradeRepository(session).list_losing(
            limit, only_unreviewed=only_unreviewed
        )
    ]


@router.post("/backfill")
def history_backfill(
    days: int = 30,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> dict:
    """Catch up on historical closed trades from the bridge over the last N days.

    Read-only against the bridge; upsert dedupes by ticket so re-running is safe.
    """
    days = max(1, min(days, 365))
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    bridge = get_configured_bridge()
    try:
        trades = bridge.closed_trades_range(start, end)
    except Exception as exc:
        logger.warning("Backfill failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Bridge could not return history: {exc}")
    repo = ClosedTradeRepository(session)
    order_by_ticket = {
        o.order_ticket: o
        for o in OrderRepository(session).list_filled_with_ticket()
        if o.order_ticket is not None
    }
    inserted = repo.upsert_from_bridge(trades, order_by_ticket)
    return {"days": days, "fetched": len(trades), "inserted": inserted}


@router.post("/review/{ticket}")
def history_save_review(
    ticket: int,
    body: TradeReview,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> dict:
    row = ClosedTradeRepository(session).save_review(
        ticket, note=body.note, reviewed_by=operator
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"No closed trade with ticket {ticket}")
    return closed_trade_to_dict(row)


@router.post("/review/{ticket}/analyze")
def history_analyze_loss(
    ticket: int,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> dict:
    row = ClosedTradeRepository(session).get_by_ticket(ticket)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No closed trade with ticket {ticket}")
    result = AnalysisService(session).analyze(
        "loss_review",
        (
            "Review this losing trade. Suggest a concise journal draft covering "
            "entry quality, risk, execution, invalidation, and one process improvement. "
            "Do not change risk rules or place an order."
        ),
        closed_trade_to_dict(row),
    )
    return analysis_result_to_dict(result)
