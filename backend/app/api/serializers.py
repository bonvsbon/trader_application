"""Row -> dict serializers for API responses (kept out of the ORM layer)."""

from __future__ import annotations

from app.persistence.entities import (
    AuditLogRow,
    ClosedTradeRow,
    LogRow,
    OrderRow,
    RiskDecisionRow,
    TradeProposalRow,
    WorkflowRunRow,
)


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def order_to_dict(o: OrderRow) -> dict:
    return {
        "id": o.id,
        "idempotency_key": o.idempotency_key,
        "symbol": o.symbol,
        "side": o.side,
        "volume": o.volume,
        "sl": o.sl,
        "tp": o.tp,
        "risk_pct": o.risk_pct,
        "source": o.source,
        "strategy_reason": o.strategy_reason,
        "ai_reason": o.ai_reason,
        "requested_by": o.requested_by,
        "state": o.state,
        "decision": o.decision,
        "account_type": o.account_type,
        "trading_mode": o.trading_mode,
        "order_ticket": o.order_ticket,
        "message": o.message,
        "created_at": _iso(o.created_at),
        "updated_at": _iso(o.updated_at),
    }


def proposal_context_to_dict(p: TradeProposalRow) -> dict:
    """Compact proposal snapshot attached to a pending-approval order."""
    return {
        "id": p.id,
        "strategy_name": p.strategy_name,
        "strategy_reason": p.strategy_reason,
        "ai_summary": p.ai_summary,
        "ai_confidence": p.ai_confidence,
        "risk_decision": p.risk_decision,
        "risk_reasons": list(p.risk_reasons or []),
        "risk_warnings": list(p.risk_warnings or []),
    }


def pending_approval_to_dict(
    o: OrderRow,
    *,
    risk: RiskDecisionRow | None = None,
    proposal: TradeProposalRow | None = None,
) -> dict:
    """Order awaiting approval, enriched with the risk decision reasons and the
    originating proposal context so the operator decides with full visibility."""
    data = order_to_dict(o)
    data["risk_reasons"] = list(risk.reasons) if risk else []
    data["risk_warnings"] = list(risk.warnings) if risk else []
    data["proposal"] = proposal_context_to_dict(proposal) if proposal else None
    return data


def audit_to_dict(a: AuditLogRow) -> dict:
    return {
        "id": a.id,
        "event": a.event,
        "idempotency_key": a.idempotency_key,
        "order_id": a.order_id,
        "symbol": a.symbol,
        "account_type": a.account_type,
        "trading_mode": a.trading_mode,
        "decision": a.decision,
        "strategy_reason": a.strategy_reason,
        "ai_reason": a.ai_reason,
        "user_approval": a.user_approval,
        "mt5_response": a.mt5_response,
        "payload": a.payload,
        "created_at": _iso(a.created_at),
    }


def risk_to_dict(r: RiskDecisionRow) -> dict:
    return {
        "id": r.id,
        "idempotency_key": r.idempotency_key,
        "symbol": r.symbol,
        "decision": r.decision,
        "reasons": r.reasons,
        "warnings": r.warnings,
        "created_at": _iso(r.created_at),
    }


def log_to_dict(log_row: LogRow) -> dict:
    return {
        "id": log_row.id,
        "level": log_row.level,
        "source": log_row.source,
        "message": log_row.message,
        "context": log_row.context,
        "created_at": _iso(log_row.created_at),
    }


def workflow_to_dict(w: WorkflowRunRow) -> dict:
    return {
        "id": w.id,
        "started_at": _iso(w.started_at),
        "finished_at": _iso(w.finished_at),
        "step": w.step,
        "status": w.status,
        "detail": w.detail,
        "error": w.error,
    }


def closed_trade_to_dict(t: ClosedTradeRow) -> dict:
    return {
        "id": t.id,
        "ticket": t.ticket,
        "symbol": t.symbol,
        "side": t.side,
        "volume": t.volume,
        "profit": t.profit,
        "close_time": _iso(t.close_time),
        "matched_order_id": t.matched_order_id,
        "planned_risk_amount": t.planned_risk_amount,
        "r_multiple": t.r_multiple,
        "synced_at": _iso(t.synced_at),
        "entry_price": t.entry_price,
        "exit_price": t.exit_price,
        "open_time": _iso(t.open_time),
        "exit_reason": t.exit_reason,
        "strategy_reason": t.strategy_reason,
        "ai_reason": t.ai_reason,
        "decision": t.decision,
        "reviewed": t.reviewed,
        "review_note": t.review_note,
        "reviewed_by": t.reviewed_by,
        "reviewed_at": _iso(t.reviewed_at),
    }


def proposal_to_dict(row: TradeProposalRow) -> dict:
    return {
        "id": row.id,
        "status": row.status,
        "symbol": row.symbol,
        "side": row.side,
        "entry_price": row.entry_price,
        "sl": row.sl,
        "tp": row.tp,
        "volume": row.volume,
        "risk_pct": row.risk_pct,
        "strategy_name": row.strategy_name,
        "strategy_reason": row.strategy_reason,
        "ai_summary": row.ai_summary,
        "ai_confidence": row.ai_confidence,
        "risk_decision": row.risk_decision,
        "risk_reasons": row.risk_reasons,
        "risk_warnings": row.risk_warnings,
        "order_idempotency_key": row.order_idempotency_key,
        "created_by": row.created_by,
        "created_at": _iso(row.created_at),
        "expires_at": _iso(row.expires_at),
        "updated_at": _iso(row.updated_at),
    }
