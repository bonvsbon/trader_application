"""Approval queue enrichment — risk reasons + originating proposal context.

A pending-approval order must carry enough context for an operator to decide:
the actual risk decision reasons, and (when it came from a proposal) the
strategy rationale and advisory AI snapshot. AI stays advisory only.
"""

from __future__ import annotations

from app.api.serializers import pending_approval_to_dict
from app.core.enums import AccountType, OrderSide, OrderState
from app.domain.models import OrderRequest, StrategyPresetConfig
from app.persistence.repositories import (
    RiskRepository,
    StrategyConfigRepository,
    TradeProposalRepository,
)
from app.strategy.proposals import ProposalService


def _real_settings(make_settings):
    return make_settings(
        allow_real_trading=True,
        api_auth_required=True,
        api_auth_token="test-token",
    )


def test_pending_approval_dict_carries_risk_and_proposal_context(
    order_service, session, make_settings
):
    svc = order_service(settings=_real_settings(make_settings), account_type=AccountType.REAL)
    StrategyConfigRepository(session).save(
        StrategyPresetConfig(enabled=True), updated_by="tester"
    )

    proposals = ProposalService(svc)
    proposal = proposals.generate(
        side=OrderSide.BUY,
        sl=2349.0,
        volume=0.1,
        strategy_reason="Manual D40/D20 breakout setup",
        created_by="tester",
        ai_summary="Trend supportive; invalidation below the 20-bar channel.",
        ai_confidence=0.62,
    )
    result = proposals.submit(proposal.id, submitted_by="tester")
    assert result.state is OrderState.PENDING_APPROVAL  # real account queues for review

    order = svc.orders.get_by_key(proposal.order_idempotency_key)
    assert order is not None

    linked = TradeProposalRepository(session).get_by_order_key(order.idempotency_key)
    assert linked is not None and linked.id == proposal.id

    risk = RiskRepository(session).latest_for(order.idempotency_key)
    assert risk is not None

    data = pending_approval_to_dict(order, risk=risk, proposal=linked)
    assert data["risk_reasons"] == list(risk.reasons)
    assert data["risk_warnings"] == list(risk.warnings)
    assert data["proposal"]["id"] == proposal.id
    assert data["proposal"]["strategy_reason"] == "Manual D40/D20 breakout setup"
    assert data["proposal"]["ai_summary"].startswith("Trend supportive")
    assert data["proposal"]["ai_confidence"] == 0.62


def test_pending_approval_dict_without_proposal_is_safe(
    order_service, session, make_settings
):
    svc = order_service(settings=_real_settings(make_settings), account_type=AccountType.REAL)

    result = svc.place_order(
        OrderRequest(
            symbol="XAUUSD",
            side=OrderSide.BUY,
            volume=0.1,
            sl=2349.0,
            risk_pct=1.0,
            idempotency_key="manual-real-approval-1",
            source="manual",
            strategy_reason="Manual desk order",
        )
    )
    assert result.state is OrderState.PENDING_APPROVAL

    order = svc.orders.get_by_key("manual-real-approval-1")
    risk = RiskRepository(session).latest_for(order.idempotency_key)
    linked = TradeProposalRepository(session).get_by_order_key(order.idempotency_key)
    assert linked is None

    data = pending_approval_to_dict(order, risk=risk, proposal=linked)
    assert data["proposal"] is None
    assert data["risk_reasons"] == list(risk.reasons)
    assert data["strategy_reason"] == "Manual desk order"
