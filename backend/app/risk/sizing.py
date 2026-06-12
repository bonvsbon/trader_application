"""Pure position-sizing calculations based on broker symbol metadata."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.core.enums import OrderSide
from app.domain.models import AccountInfo, OrderRequest, Position, SymbolInfo, SymbolQuote


@dataclass(frozen=True)
class PositionSizing:
    entry_price: float
    loss_per_lot: float
    estimated_loss: float
    estimated_reward: float | None
    sized_risk_pct: float
    max_volume_for_risk: float


def entry_price(request: OrderRequest, quote: SymbolQuote) -> float:
    return quote.ask if request.side is OrderSide.BUY else quote.bid


def price_directions_valid(request: OrderRequest, entry: float) -> list[str]:
    problems: list[str] = []
    if request.sl is None:
        problems.append("Stop loss is required")
        return problems
    if request.side is OrderSide.BUY:
        if request.sl >= entry:
            problems.append("BUY stop loss must be below the entry price")
        if request.tp is not None and request.tp <= entry:
            problems.append("BUY take profit must be above the entry price")
    else:
        if request.sl <= entry:
            problems.append("SELL stop loss must be above the entry price")
        if request.tp is not None and request.tp >= entry:
            problems.append("SELL take profit must be below the entry price")
    return problems


def volume_aligned(volume: float, step: float) -> bool:
    units = volume / step
    return math.isclose(units, round(units), rel_tol=0.0, abs_tol=1e-8)


def floor_volume(volume: float, info: SymbolInfo) -> float:
    capped = min(volume, info.volume_max)
    units = math.floor((capped + 1e-12) / info.volume_step)
    result = units * info.volume_step
    if result < info.volume_min:
        return 0.0
    precision = max(0, len(f"{info.volume_step:.10f}".rstrip("0").split(".")[-1]))
    return round(result, precision)


def calculate_position_sizing(
    request: OrderRequest,
    quote: SymbolQuote,
    info: SymbolInfo,
    account: AccountInfo,
) -> PositionSizing | None:
    if request.sl is None or request.risk_pct is None or account.equity <= 0:
        return None
    entry = entry_price(request, quote)
    if price_directions_valid(request, entry):
        return None
    ticks_to_sl = abs(entry - request.sl) / info.tick_size
    loss_per_lot = ticks_to_sl * info.tick_value
    if loss_per_lot <= 0:
        return None
    allowed_loss = account.equity * request.risk_pct / 100.0
    max_volume = floor_volume(allowed_loss / loss_per_lot, info)
    estimated_loss = loss_per_lot * request.volume
    estimated_reward = None
    if request.tp is not None:
        ticks_to_tp = abs(request.tp - entry) / info.tick_size
        estimated_reward = ticks_to_tp * info.tick_value * request.volume
    return PositionSizing(
        entry_price=entry,
        loss_per_lot=loss_per_lot,
        estimated_loss=estimated_loss,
        estimated_reward=estimated_reward,
        sized_risk_pct=(estimated_loss / account.equity) * 100.0,
        max_volume_for_risk=max_volume,
    )


def position_risk_amount(position: Position, info: SymbolInfo) -> float | None:
    if position.sl is None:
        return None
    ticks_to_sl = abs(position.open_price - position.sl) / info.tick_size
    return ticks_to_sl * info.tick_value * position.volume
