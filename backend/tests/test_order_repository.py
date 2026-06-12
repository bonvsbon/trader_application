"""Database-level atomic order reservation and state claiming."""

from __future__ import annotations

from app.core.enums import AccountType, OrderSide, OrderState, RiskDecision, TradingMode
from app.domain.models import OrderRequest
from app.execution.idempotency import make_duplicate_fingerprint
from app.persistence.repositories import OrderRepository


def _request(key: str) -> OrderRequest:
    return OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.1,
        sl=2349.0,
        risk_pct=1.0,
        idempotency_key=key,
    )


def test_reservation_rejects_same_fingerprint_with_different_key(session):
    repo = OrderRepository(session)
    first_request = _request("reserve-first-123")
    fingerprint = make_duplicate_fingerprint(first_request)
    first, conflict = repo.reserve(
        first_request,
        state=OrderState.PENDING.value,
        decision=RiskDecision.BLOCK.value,
        account_type=AccountType.UNKNOWN.value,
        trading_mode=TradingMode.MANUAL_ONLY.value,
        dedupe_fingerprint=fingerprint,
    )
    assert first is not None
    assert conflict is None

    second, conflict = repo.reserve(
        _request("reserve-second-12"),
        state=OrderState.PENDING.value,
        decision=RiskDecision.BLOCK.value,
        account_type=AccountType.UNKNOWN.value,
        trading_mode=TradingMode.MANUAL_ONLY.value,
        dedupe_fingerprint=fingerprint,
    )
    assert second is None
    assert conflict is not None
    assert conflict.id == first.id


def test_state_claim_only_succeeds_once(session):
    repo = OrderRepository(session)
    request = _request("claim-state-1234")
    row = repo.create(
        request,
        state=OrderState.PENDING_APPROVAL.value,
        decision=RiskDecision.ALLOW.value,
        account_type=AccountType.REAL.value,
        trading_mode=TradingMode.MANUAL_ONLY.value,
    )
    assert repo.claim_state(
        row.id,
        expected=OrderState.PENDING_APPROVAL.value,
        new=OrderState.APPROVED.value,
    )
    assert not repo.claim_state(
        row.id,
        expected=OrderState.PENDING_APPROVAL.value,
        new=OrderState.APPROVED.value,
    )
