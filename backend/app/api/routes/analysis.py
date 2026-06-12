"""Advisory analysis runtime and provenance API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.service import AnalysisResult, AnalysisService
from app.api.auth import get_operator
from app.persistence.db import get_db
from app.persistence.repositories import AnalysisSnapshotRepository
from app.providers.models import ANALYSIS_CAPABILITIES, AnalysisCapability

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class AnalysisRunRequest(BaseModel):
    capability: AnalysisCapability
    prompt: str = Field(min_length=3, max_length=4000)
    context: dict = Field(default_factory=dict)


def analysis_result_to_dict(result: AnalysisResult) -> dict:
    return {
        "available": result.available,
        "capability": result.capability,
        "correlation_id": result.correlation_id,
        "summary": result.summary,
        "confidence": result.confidence,
        "provider_id": result.provider_id,
        "provider_name": result.provider_name,
        "provider_type": result.provider_type,
        "model_or_tool": result.model_or_tool,
        "attempts": [attempt.__dict__ for attempt in result.attempts],
    }


@router.get("/capabilities")
def analysis_capabilities(operator: str = Depends(get_operator)) -> list[str]:
    return list(ANALYSIS_CAPABILITIES)


@router.post("/run")
def run_analysis(
    body: AnalysisRunRequest,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> dict:
    return analysis_result_to_dict(
        AnalysisService(session).analyze(body.capability, body.prompt, body.context)
    )


@router.get("/snapshots")
def analysis_snapshots(
    limit: int = 100,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> list[dict]:
    return [
        {
            "id": row.id,
            "correlation_id": row.correlation_id,
            "capability": row.capability,
            "provider_id": row.provider_id,
            "provider_type": row.provider_type,
            "provider_name": row.provider_name,
            "model_or_tool": row.model_or_tool,
            "success": row.success,
            "latency_ms": row.latency_ms,
            "output_summary": row.output_summary,
            "error": row.error,
            "created_at": row.created_at.isoformat(),
        }
        for row in AnalysisSnapshotRepository(session).list_recent(
            max(1, min(limit, 500))
        )
    ]
