"""WebSocket — pushes interval workflow status (incl. countdown) once per second."""

from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.auth.service import AuthService
from app.bridge.base import get_configured_bridge, get_effective_mt5_config
from app.core.config import get_settings
from app.domain.models import SymbolQuote
from app.market_data.alpaca import alpaca_quote_stream
from app.market_data.base import load_market_data_config
from app.workflow.scheduler import get_scheduler

router = APIRouter()
_SYMBOL_RE = re.compile(r"^[A-Za-z0-9._-]{1,32}$")


def _websocket_authenticated(websocket: WebSocket) -> bool:
    settings = get_settings()
    if not settings.user_auth_enabled:
        return True
    from app.persistence.db import SessionLocal

    with SessionLocal() as session:
        context = AuthService(session, settings).context_for_token(
            websocket.cookies.get(settings.auth_cookie_name, "")
        )
        session.commit()
        return context is not None


def _simulated_tick(quote: SymbolQuote, walk: dict[str, float]) -> dict:
    """Overlay a small, bounded mean-reverting random walk on the mock bridge's
    static quote so the watchlist visibly streams in dev without a live feed.

    Display only — the deterministic `bridge.quote()` used for risk sizing and
    execution is never altered. Real bridges already return moving prices, so
    this is applied to the mock bridge alone.
    """
    mid = (quote.bid + quote.ask) / 2
    half = (quote.ask - quote.bid) / 2
    drift = walk.get(quote.symbol, 0.0) * 0.9  # decay toward the reference mid
    drift += random.uniform(-1.0, 1.0) * mid * 0.0004
    drift = max(-mid * 0.02, min(mid * 0.02, drift))  # clamp to ±2%
    walk[quote.symbol] = drift
    live_mid = mid + drift
    return {
        "symbol": quote.symbol,
        "bid": round(live_mid - half, 2),
        "ask": round(live_mid + half, 2),
        "spread_points": quote.spread_points,
        "time": datetime.now(timezone.utc).isoformat(),
    }


def _mt5_quote_error(symbol: str, exc: Exception) -> dict:
    message = (str(exc) or type(exc).__name__)[:300]
    lowered = message.lower()
    if "quote unavailable" in lowered or "symbol" in lowered:
        return {
            "symbol": symbol,
            "error": message,
            "code": "broker_symbol_unavailable",
            "hint": (
                "This exact symbol is unavailable from the connected MT5 broker. "
                "Use the broker's symbol name (it may include a suffix) or configure "
                "Alpaca IEX in Market Data for US stocks."
            ),
        }
    return {
        "symbol": symbol,
        "error": message,
        "code": "mt5_quote_failed",
        "hint": "Check the MT5 bridge connection and confirm the symbol is visible in Market Watch.",
    }


@router.websocket("/ws/status")
async def ws_status(websocket: WebSocket) -> None:
    if not _websocket_authenticated(websocket):
        await websocket.close(code=1008, reason="Login required")
        return
    await websocket.accept()
    scheduler = get_scheduler()
    try:
        while True:
            await websocket.send_json(scheduler.status())
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


@router.websocket("/ws/market")
async def ws_market(
    websocket: WebSocket,
    symbols: str = Query(default="", max_length=1000),
) -> None:
    """Stream read-only quotes. This endpoint never submits an order."""
    if not _websocket_authenticated(websocket):
        await websocket.close(code=1008, reason="Login required")
        return
    config = load_market_data_config()
    symbol_values = symbols.split(",") if symbols else config.default_symbols
    requested = list(
        dict.fromkeys(
            value.strip().upper()
            for value in symbol_values
            if value.strip()
        )
    )
    if not requested or len(requested) > config.max_symbols or any(
        not _SYMBOL_RE.fullmatch(symbol) for symbol in requested
    ):
        await websocket.close(code=1008, reason="Invalid symbol list")
        return

    await websocket.accept()
    if not config.enabled or config.provider == "disabled":
        await websocket.send_json(
            {
                "source": "disabled",
                "feed_status": "disabled",
                "quotes": [],
                "errors": [{"symbol": "*", "error": "Market-data provider is disabled"}],
            }
        )
        await websocket.close(code=1000)
        return

    if config.provider == "alpaca":
        source = f"alpaca:{config.feed}"
        try:
            async for quote in alpaca_quote_stream(
                config,
                requested,
                get_settings(),
            ):
                await websocket.send_json(
                    {
                        "source": source,
                        "feed_status": config.feed_status,
                        "quotes": [quote],
                        "errors": [],
                    }
                )
        except WebSocketDisconnect:
            return
        except Exception as exc:
            try:
                await websocket.send_json(
                    {
                        "source": source,
                        "feed_status": config.feed_status,
                        "quotes": [],
                        "errors": [{"symbol": "*", "error": str(exc)[:300]}],
                    }
                )
                await websocket.close(code=1011)
            except WebSocketDisconnect:
                pass
        return

    bridge = get_configured_bridge()
    bridge_type = get_effective_mt5_config().bridge_type
    source = f"mt5:{bridge_type}"
    simulate_live = bridge_type == "mock"
    # A real bridge (e.g. ea_socket) serializes every RPC over one connection,
    # so a 1s watchlist tick starves heavier reads (dashboard/risk preview).
    # The mock bridge is in-memory, so it can stream fast for a lively demo.
    tick_seconds = 1.0 if simulate_live else 2.5
    walk: dict[str, float] = {}
    try:
        while True:
            quotes: list[dict] = []
            errors: list[dict] = []
            for symbol in requested:
                try:
                    quote = await asyncio.to_thread(bridge.quote, symbol)
                    quotes.append(
                        _simulated_tick(quote, walk)
                        if simulate_live
                        else quote.model_dump(mode="json")
                    )
                except Exception as exc:
                    errors.append(_mt5_quote_error(symbol, exc))
            await websocket.send_json(
                {
                    "source": source,
                    "feed_status": config.feed_status,
                    "quotes": quotes,
                    "errors": errors,
                }
            )
            await asyncio.sleep(tick_seconds)
    except WebSocketDisconnect:
        return
