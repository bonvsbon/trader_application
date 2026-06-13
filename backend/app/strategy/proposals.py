"""Trade proposal generation without bypassing the order chokepoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.ai.service import AnalysisService
from app.core.enums import OrderSide, RiskDecision
from app.domain.models import OrderRequest, OrderResult
from app.execution.order_service import OrderService
from app.persistence.entities import TradeProposalRow
from app.persistence.repositories import (
    AuditRepository,
    StrategyConfigRepository,
    TradeProposalRepository,
)
from app.strategy.base import default_strategy_config


class ProposalError(ValueError):
    pass


class ProposalService:
    def __init__(self, order_service: OrderService) -> None:
        self.order_service = order_service
        self.session = order_service.session
        self.settings = order_service.settings
        account_id = order_service.mt5_account_id
        self.proposals = TradeProposalRepository(self.session, account_id)
        self.strategy_configs = StrategyConfigRepository(self.session, account_id)
        self.audit = AuditRepository(self.session, account_id)

    def generate(
        self,
        *,
        side: OrderSide,
        sl: float,
        volume: float | None,
        strategy_reason: str,
        created_by: str,
        ai_summary: str | None = None,
        ai_confidence: float | None = None,
        order_idempotency_key: str | None = None,
    ) -> TradeProposalRow:
        config = self.strategy_configs.get_config() or default_strategy_config(self.settings)
        if not config.enabled:
            raise ProposalError("Strategy preset is disabled")

        quote = self.order_service.bridge.quote(config.symbol)
        symbol_info = self.order_service.bridge.symbol_info(config.symbol)
        entry = quote.ask if side is OrderSide.BUY else quote.bid
        risk_distance = entry - sl if side is OrderSide.BUY else sl - entry
        if risk_distance <= 0:
            raise ProposalError("Stop loss must be below BUY entry or above SELL entry")
        tp = (
            entry + risk_distance * config.reward_risk_ratio
            if side is OrderSide.BUY
            else entry - risk_distance * config.reward_risk_ratio
        )

        selected_volume = volume or symbol_info.volume_min
        request = self._preview_request(
            config.symbol,
            side,
            selected_volume,
            sl,
            tp,
            config.risk_pct,
            strategy_reason,
        )
        risk, context = self.order_service.preview(request)
        if volume is None and context.max_volume_for_risk is not None:
            selected_volume = max(
                symbol_info.volume_min,
                min(
                    context.max_volume_for_risk,
                    symbol_info.volume_max,
                    self.settings.risk_max_order_volume_lots,
                ),
            )
            request = self._preview_request(
                config.symbol,
                side,
                selected_volume,
                sl,
                tp,
                config.risk_pct,
                strategy_reason,
            )
            risk, context = self.order_service.preview(request)

        if config.require_news_clear and not context.news.is_live:
            risk = risk.model_copy(
                update={
                    "decision": RiskDecision.BLOCK,
                    "reasons": [
                        *risk.reasons,
                        "Strategy requires live news clearance, but the provider is unavailable",
                    ],
                }
            )

        if ai_summary is None:
            analysis = AnalysisService(
                self.session, self.settings, mt5_account_id=self.order_service.mt5_account_id
            ).analyze(
                "proposal_explanation",
                (
                    "Explain this trade proposal concisely. Identify supporting facts, "
                    "risks, and invalidation conditions. Do not approve or place an order."
                ),
                {
                    "symbol": config.symbol,
                    "side": side.value,
                    "entry_price": entry,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "volume": selected_volume,
                    "risk_pct": config.risk_pct,
                    "strategy_name": config.preset_name,
                    "strategy_reason": strategy_reason,
                    "risk_decision": risk.decision.value,
                    "risk_reasons": list(risk.reasons),
                    "risk_warnings": list(risk.warnings),
                    "news": context.news.model_dump(mode="json"),
                    "volatility": context.volatility.model_dump(mode="json"),
                },
            )
            ai_summary = analysis.summary
            ai_confidence = analysis.confidence if analysis.available else None

        status = "BLOCKED" if risk.decision is RiskDecision.BLOCK else "DRAFT"
        row = self.proposals.create(
            status=status,
            symbol=config.symbol,
            side=side.value,
            entry_price=entry,
            sl=sl,
            tp=tp,
            volume=selected_volume,
            risk_pct=config.risk_pct,
            strategy_name=config.preset_name,
            strategy_reason=strategy_reason,
            ai_summary=ai_summary,
            ai_confidence=ai_confidence,
            risk_decision=risk.decision.value,
            risk_reasons=list(risk.reasons),
            risk_warnings=list(risk.warnings),
            order_idempotency_key=order_idempotency_key,
            created_by=created_by,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=self.settings.proposal_expiry_minutes),
        )
        self.audit.write(
            event="proposal.generated",
            symbol=row.symbol,
            decision=row.risk_decision,
            strategy_reason=row.strategy_reason,
            ai_reason=row.ai_summary,
            payload={
                "proposal_id": row.id,
                "status": row.status,
                "entry_price": row.entry_price,
                "sl": row.sl,
                "tp": row.tp,
                "volume": row.volume,
                "signal_definition_confirmed": config.signal_definition_confirmed,
            },
        )
        return row

    def submit(
        self,
        proposal_id: int,
        *,
        submitted_by: str,
        source: str = "manual",
    ) -> OrderResult:
        row = self.proposals.get(proposal_id)
        if row is None:
            raise ProposalError(f"No trade proposal with id {proposal_id}")
        if self._is_expired(row):
            self.proposals.update_status(row, "EXPIRED")
            raise ProposalError("Trade proposal expired; generate a new proposal")
        if row.status not in {"DRAFT", "PENDING_APPROVAL", "FILLED", "RISK_BLOCKED"}:
            raise ProposalError(f"Trade proposal cannot be submitted from status {row.status}")

        key = row.order_idempotency_key or f"proposal-{row.id}-{uuid4().hex[:16]}"
        self.proposals.update_status(row, row.status, order_idempotency_key=key)
        request = OrderRequest(
            symbol=row.symbol,
            side=OrderSide(row.side),
            volume=row.volume,
            sl=row.sl,
            tp=row.tp,
            risk_pct=row.risk_pct,
            idempotency_key=key,
            source=source,
            strategy_reason=row.strategy_reason,
            ai_reason=row.ai_summary,
            requested_by=submitted_by,
        )
        result = self.order_service.place_order(request)
        self.proposals.update_status(row, result.state.value)
        self.audit.write(
            event="proposal.submitted",
            idempotency_key=key,
            order_id=result.order_id,
            symbol=row.symbol,
            account_type=result.account_type.value,
            trading_mode=result.trading_mode.value,
            decision=result.decision.value,
            strategy_reason=row.strategy_reason,
            ai_reason=row.ai_summary,
            payload={
                "proposal_id": row.id,
                "submitted_by": submitted_by,
                "order_state": result.state.value,
            },
        )
        return result

    @staticmethod
    def _preview_request(
        symbol: str,
        side: OrderSide,
        volume: float,
        sl: float,
        tp: float,
        risk_pct: float,
        strategy_reason: str,
    ) -> OrderRequest:
        return OrderRequest(
            symbol=symbol,
            side=side,
            volume=volume,
            sl=sl,
            tp=tp,
            risk_pct=risk_pct,
            idempotency_key=f"proposal-preview-{uuid4().hex}",
            source="manual",
            strategy_reason=strategy_reason,
            requested_by="proposal-preview",
        )

    @staticmethod
    def _is_expired(row: TradeProposalRow) -> bool:
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires_at
