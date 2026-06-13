from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.ai.service import AnalysisResult
from app.news.base import RoutedMcpNewsProvider, create_news_provider


def _result(payload: dict) -> AnalysisResult:
    return AnalysisResult(
        capability="economic_calendar",
        correlation_id="calendar-test",
        summary=json.dumps(payload),
        provider_type="mcp",
    )


def _payload(*, generated_at: datetime, events: list[dict]) -> dict:
    return {
        "generated_at": generated_at.isoformat(),
        "events": events,
    }


def test_routed_calendar_marks_nearby_usd_high_impact_event(
    session,
    make_settings,
    monkeypatch,
):
    now = datetime.now(timezone.utc)
    provider = RoutedMcpNewsProvider(session, make_settings())
    monkeypatch.setattr(
        provider.analysis,
        "analyze",
        lambda *args, **kwargs: _result(
            _payload(
                generated_at=now,
                events=[
                    {
                        "title": "US CPI",
                        "currency": "USD",
                        "impact": "high",
                        "starts_at": (now + timedelta(minutes=10)).isoformat(),
                    }
                ],
            )
        ),
    )

    risk = provider.news_risk("XAUUSD")

    assert risk.is_live is True
    assert risk.has_high_impact_within_window is True
    assert risk.minutes_to_next_high_impact == pytest.approx(10, abs=0.1)
    assert "US CPI" in risk.summary


def test_routed_calendar_ignores_unrelated_or_distant_events(
    session,
    make_settings,
    monkeypatch,
):
    now = datetime.now(timezone.utc)
    provider = RoutedMcpNewsProvider(session, make_settings())
    monkeypatch.setattr(
        provider.analysis,
        "analyze",
        lambda *args, **kwargs: _result(
            _payload(
                generated_at=now,
                events=[
                    {
                        "title": "ECB speech",
                        "currency": "EUR",
                        "impact": "high",
                        "starts_at": (now + timedelta(minutes=5)).isoformat(),
                    },
                    {
                        "title": "US payrolls",
                        "currency": "USD",
                        "impact": "high",
                        "starts_at": (now + timedelta(hours=2)).isoformat(),
                    },
                ],
            )
        ),
    )

    risk = provider.news_risk("XAUUSD")

    assert risk.is_live is True
    assert risk.has_high_impact_within_window is False


def test_routed_calendar_rejects_stale_or_malformed_data(
    session,
    make_settings,
    monkeypatch,
):
    provider = RoutedMcpNewsProvider(
        session,
        make_settings(news_max_age_minutes=15),
    )
    stale = datetime.now(timezone.utc) - timedelta(minutes=30)
    monkeypatch.setattr(
        provider.analysis,
        "analyze",
        lambda *args, **kwargs: _result(
            _payload(generated_at=stale, events=[])
        ),
    )

    with pytest.raises(RuntimeError, match="stale"):
        provider.news_risk("XAUUSD")

    monkeypatch.setattr(
        provider.analysis,
        "analyze",
        lambda *args, **kwargs: AnalysisResult(
            capability="economic_calendar",
            correlation_id="bad-json",
            summary="not json",
        ),
    )
    with pytest.raises(json.JSONDecodeError):
        provider.news_risk("XAUUSD")


def test_routed_calendar_restricts_risk_route_to_mcp(
    session,
    make_settings,
    monkeypatch,
):
    provider = RoutedMcpNewsProvider(session, make_settings())
    captured: dict = {}

    def fake_analyze(*args, **kwargs):
        captured.update(kwargs)
        return AnalysisResult(
            capability="economic_calendar",
            correlation_id="missing-route",
            summary=None,
        )

    monkeypatch.setattr(provider.analysis, "analyze", fake_analyze)

    with pytest.raises(RuntimeError, match="No healthy MCP"):
        provider.news_risk("XAUUSD")
    assert captured["allowed_provider_types"] == {"mcp"}


def test_routed_calendar_factory_requires_database_session(make_settings):
    with pytest.raises(ValueError, match="Database session is required"):
        create_news_provider(make_settings(news_provider="routed_mcp"))
