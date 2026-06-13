"""Editable XAUUSD preset and persisted trade proposals."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import get_operator
from app.api.deps import get_order_service
from app.api.serializers import proposal_to_dict
from app.core.enums import OrderSide
from app.domain.models import StrategyPresetConfig
from app.execution.order_service import OrderService
from app.persistence.repositories import (
    AuditRepository,
    StrategyConfigRepository,
    TradeProposalRepository,
)
from app.strategy.backtest import BacktestService
from app.strategy.base import default_strategy_config
from app.strategy.proposals import ProposalError, ProposalService
from app.strategy.signal import SignalService

router = APIRouter(prefix="/api", tags=["strategy"])


class ProposalCreate(BaseModel):
    side: OrderSide
    sl: float = Field(gt=0)
    volume: float | None = Field(default=None, gt=0)
    strategy_reason: str = Field(min_length=5, max_length=1000)
    ai_summary: str | None = Field(default=None, max_length=4000)
    ai_confidence: float | None = Field(default=None, ge=0, le=1)


@router.get("/strategy/configuration")
def strategy_configuration(
    svc: OrderService = Depends(get_order_service),
    operator: str = Depends(get_operator),
) -> dict:
    repository = StrategyConfigRepository(svc.session, svc.mt5_account_id)
    row = repository.get()
    config = repository.get_config() or default_strategy_config(svc.settings)
    return {
        **config.model_dump(mode="json"),
        "source": "database" if row else "environment",
        "updated_by": row.updated_by if row else None,
        "updated_at": row.updated_at.isoformat() if row else None,
    }


@router.put("/strategy/configuration")
def update_strategy_configuration(
    config: StrategyPresetConfig,
    svc: OrderService = Depends(get_order_service),
    operator: str = Depends(get_operator),
) -> dict:
    if config.risk_pct > svc.settings.risk_max_risk_per_trade_pct:
        raise HTTPException(
            status_code=422,
            detail="Strategy risk exceeds the global maximum risk per trade",
        )
    row = StrategyConfigRepository(
        svc.session, svc.mt5_account_id
    ).save(config, updated_by=operator)
    AuditRepository(svc.session, svc.mt5_account_id).write(
        event="strategy.configuration_updated",
        symbol=config.symbol,
        strategy_reason=config.preset_name,
        payload={**config.model_dump(mode="json"), "updated_by": operator},
    )
    return {
        **config.model_dump(mode="json"),
        "source": "database",
        "updated_by": row.updated_by,
        "updated_at": row.updated_at.isoformat(),
    }


@router.post("/proposals")
def generate_proposal(
    body: ProposalCreate,
    svc: OrderService = Depends(get_order_service),
    operator: str = Depends(get_operator),
) -> dict:
    try:
        row = ProposalService(svc).generate(
            side=body.side,
            sl=body.sl,
            volume=body.volume,
            strategy_reason=body.strategy_reason,
            created_by=operator,
            ai_summary=body.ai_summary,
            ai_confidence=body.ai_confidence,
        )
    except ProposalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return proposal_to_dict(row)


@router.post("/strategy/evaluate-signal")
def evaluate_signal(
    svc: OrderService = Depends(get_order_service),
    operator: str = Depends(get_operator),
) -> dict:
    """Evaluate the gated D40/D20 Donchian signal. On a breakout it creates a
    trade proposal (which still requires human approval); it never trades."""
    try:
        result = SignalService(ProposalService(svc)).evaluate(created_by=operator)
    except ProposalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    signal = None
    if result.signal is not None:
        signal = {
            "side": result.signal.side.value,
            "breakout_level": result.signal.breakout_level,
            "stop_loss": result.signal.stop_loss,
            "reason": result.signal.reason,
        }
    return {
        "reason": result.reason,
        "signal": signal,
        "proposal": proposal_to_dict(result.proposal) if result.proposal else None,
    }


@router.post("/strategy/backtest")
def backtest_signal(
    count: int = 500,
    svc: OrderService = Depends(get_order_service),
    operator: str = Depends(get_operator),
) -> dict:
    """Idealized D40/D20 rule backtest over recent candles. Read-only analysis —
    it never creates a proposal or trades. Results are a sanity check, not a
    profitability forecast (close-to-close fills, no spread/slippage)."""
    result = BacktestService(svc).run(count=count)
    return {
        "candles": result.candles,
        "trades": result.trades,
        "wins": result.wins,
        "losses": result.losses,
        "open_trades": result.open_trades,
        "win_rate": result.win_rate,
        "total_r": result.total_r,
        "avg_r": result.avg_r,
        "max_drawdown_r": result.max_drawdown_r,
        "reward_risk": result.reward_risk,
        "d40": result.d40,
        "d20": result.d20,
        "trade_log": [
            {
                "side": t.side,
                "entry_index": t.entry_index,
                "entry_price": t.entry_price,
                "stop_loss": t.stop_loss,
                "take_profit": t.take_profit,
                "exit_index": t.exit_index,
                "exit_price": t.exit_price,
                "outcome": t.outcome,
                "r_multiple": t.r_multiple,
            }
            for t in result.trade_log
        ],
    }


@router.get("/proposals")
def recent_proposals(
    limit: int = 50,
    svc: OrderService = Depends(get_order_service),
    operator: str = Depends(get_operator),
) -> list[dict]:
    return [
        proposal_to_dict(row)
        for row in TradeProposalRepository(
            svc.session, svc.mt5_account_id
        ).list_recent(limit)
    ]


@router.post("/proposals/{proposal_id}/submit")
def submit_proposal(
    proposal_id: int,
    svc: OrderService = Depends(get_order_service),
    operator: str = Depends(get_operator),
):
    try:
        return ProposalService(svc).submit(proposal_id, submitted_by=operator)
    except ProposalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
