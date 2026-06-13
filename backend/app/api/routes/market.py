"""Read-only market data — OHLC candles for the chart.

This endpoint is display/analysis only. Like the watchlist WebSocket it never
submits an order, and order risk/execution continue to use ``bridge.quote``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_order_service
from app.core.logging import get_logger
from app.execution.order_service import OrderService

router = APIRouter(prefix="/api/market", tags=["market"])
logger = get_logger(__name__)

VALID_TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")


@router.get("/candles")
def candles(
    symbol: str = Query("XAUUSD"),
    timeframe: str = Query("H1"),
    count: int = Query(200, ge=10, le=1000),
    svc: OrderService = Depends(get_order_service),
) -> dict:
    """Recent OHLC bars for one symbol/timeframe straight from the bridge.

    Returns an empty series with an ``error`` string when the bridge is
    unavailable instead of failing the request, so the chart can show a clear
    "feed unavailable" state rather than a 500.
    """
    sym = symbol.strip().upper() or "XAUUSD"
    tf = timeframe.strip().upper()
    if tf not in VALID_TIMEFRAMES:
        tf = "H1"
    try:
        bars = svc.bridge.candles(sym, tf, count)
    except Exception as exc:  # bridge transport / availability failure — never a silent 500
        logger.warning("candle fetch failed for %s %s: %s", sym, tf, exc)
        return {"symbol": sym, "timeframe": tf, "candles": [], "error": str(exc)}
    return {
        "symbol": sym,
        "timeframe": tf,
        "candles": [
            {
                "time": c.time.isoformat(),
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in bars
        ],
    }
