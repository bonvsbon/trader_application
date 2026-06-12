"""Logs — system logs, audit trail, and risk-decision history."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_operator
from app.api.serializers import audit_to_dict, log_to_dict, risk_to_dict
from app.persistence.db import get_db
from app.persistence.repositories import AuditRepository, LogRepository, RiskRepository

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
def system_logs(
    limit: int = 100,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> list[dict]:
    return [log_to_dict(x) for x in LogRepository(session).list_recent(limit)]


@router.get("/audit")
def audit_logs(
    limit: int = 100,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> list[dict]:
    return [audit_to_dict(x) for x in AuditRepository(session).list_recent(limit)]


@router.get("/risk")
def risk_logs(
    limit: int = 100,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> list[dict]:
    return [risk_to_dict(x) for x in RiskRepository(session).list_recent(limit)]
