from __future__ import annotations

from fastapi.testclient import TestClient

from app.ai.service import AnalysisService
from app.core.config import get_settings
from app.main import create_app
from app.persistence.db import get_db
from app.persistence.entities import AnalysisProviderRow
from app.persistence.repositories import AnalysisSnapshotRepository


def _local_provider(provider_id: int, priority: int, name: str) -> AnalysisProviderRow:
    return AnalysisProviderRow(
        id=provider_id,
        display_name=name,
        provider_type="local",
        enabled=True,
        endpoint="http://127.0.0.1:3000",
        model_name="qwen3.5:9b",
        web_search_enabled=False,
        timeout_sec=5,
        priority=priority,
        capabilities=["proposal_explanation"],
        allowed_tools=[],
        capability_tools={},
        health="HEALTHY",
    )


def test_analysis_service_fails_over_and_records_provenance(
    session,
    make_settings,
    monkeypatch,
):
    session.add_all(
        [
            _local_provider(1, 1, "Primary"),
            _local_provider(2, 2, "Fallback"),
        ]
    )
    session.flush()
    calls = 0

    def fake_analyze(self, prompt, context):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("primary unavailable")
        return {
            "summary": "Fallback analysis token=provider-secret",
            "confidence": 0.25,
        }

    monkeypatch.setattr("app.ai.service.OpenWebUIProvider.analyze", fake_analyze)

    result = AnalysisService(session, make_settings()).analyze(
        "proposal_explanation",
        "Explain with Bearer caller-secret and OPENAI_API_KEY=also-secret",
        {
            "symbol": "XAUUSD",
            "api_key": "must-not-persist",
            "market_data_alpaca_secret": "also-must-not-persist",
        },
    )

    assert result.available is True
    assert result.provider_name == "Fallback"
    assert len(result.attempts) == 2
    snapshots = list(reversed(AnalysisSnapshotRepository(session).list_recent()))
    assert [row.success for row in snapshots] == [False, True]
    assert snapshots[0].input_summary["context"]["api_key"] == "[redacted]"
    assert snapshots[0].input_summary["prompt"] == (
        "Explain with Bearer [redacted] and OPENAI_API_KEY=[redacted]"
    )
    assert (
        snapshots[0].input_summary["context"]["market_data_alpaca_secret"]
        == "[redacted]"
    )
    assert snapshots[1].output_summary == "Fallback analysis token=[redacted]"


def test_analysis_service_records_missing_route(session, make_settings):
    result = AnalysisService(session, make_settings()).analyze(
        "loss_review",
        "Review",
        {"ticket": 123},
    )

    assert result.available is False
    snapshot = AnalysisSnapshotRepository(session).list_recent()[0]
    assert snapshot.provider_id is None
    assert "No enabled healthy provider" in snapshot.error


def test_analysis_service_uses_openai_provider(
    session,
    make_settings,
    monkeypatch,
):
    row = AnalysisProviderRow(
        id=1,
        display_name="OpenAI fallback",
        provider_type="openai",
        enabled=True,
        endpoint="https://api.openai.com/v1",
        model_name="gpt-5.5",
        secret_ref="ANALYSIS_PROVIDER_OPENAI_KEY",
        timeout_sec=5,
        priority=1,
        capabilities=["proposal_explanation"],
        allowed_tools=[],
        capability_tools={},
        health="HEALTHY",
    )
    session.add(row)
    session.flush()
    monkeypatch.setattr(
        "app.ai.service.OpenAIProvider.analyze",
        lambda self, prompt, context: {
            "summary": "Cloud fallback result",
            "confidence": 0.0,
        },
    )

    result = AnalysisService(session, make_settings()).analyze(
        "proposal_explanation",
        "Explain",
        {"symbol": "XAUUSD"},
    )

    assert result.available is True
    assert result.provider_type == "openai"
    assert result.model_or_tool == "gpt-5.5"
    assert result.summary == "Cloud fallback result"


def test_analysis_api_rejects_unknown_capability(session, make_settings):
    app = create_app()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: make_settings()

    with TestClient(app) as client:
        response = client.post(
            "/api/analysis/run",
            json={
                "capability": "execute_order",
                "prompt": "This capability must never exist",
                "context": {},
            },
        )

    assert response.status_code == 422
