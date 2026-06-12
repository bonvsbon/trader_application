"""Interval workflow control — status / start / stop / manual run / history."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_operator
from app.api.serializers import workflow_to_dict
from app.persistence.db import get_db
from app.persistence.repositories import WorkflowRepository
from app.workflow.scheduler import get_scheduler

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


@router.get("/status")
def workflow_status() -> dict:
    return get_scheduler().status()


@router.post("/start")
def workflow_start(operator: str = Depends(get_operator)) -> dict:
    return get_scheduler().start()


@router.post("/stop")
def workflow_stop(operator: str = Depends(get_operator)) -> dict:
    return get_scheduler().stop()


@router.post("/run")
def workflow_run_once(operator: str = Depends(get_operator)) -> dict:
    return {"summary": get_scheduler().run_once_now(), "status": get_scheduler().status()}


@router.get("/runs")
def workflow_runs(
    limit: int = 20,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> list[dict]:
    return [workflow_to_dict(w) for w in WorkflowRepository(session).list_recent(limit)]
