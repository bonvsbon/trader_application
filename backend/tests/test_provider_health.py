from __future__ import annotations

import asyncio

from app.persistence.entities import AnalysisProviderRow, utcnow
from app.persistence.repositories import AnalysisProviderRepository
from app.providers import health as provider_health


def _mcp_provider(provider_id: int, name: str) -> AnalysisProviderRow:
    return AnalysisProviderRow(
        id=provider_id,
        display_name=name,
        provider_type="mcp",
        enabled=True,
        transport="streamable_http",
        endpoint="http://127.0.0.1:9000/mcp",
        timeout_sec=5,
        priority=provider_id,
        capabilities=["news_search"],
        allowed_tools=["search_news"],
        capability_tools={"news_search": "search_news"},
        discovered_tools=[{"name": "previous_tool"}],
        discovered_models=[],
        health="UNKNOWN",
    )


def _local_provider(provider_id: int, name: str) -> AnalysisProviderRow:
    return AnalysisProviderRow(
        id=provider_id,
        display_name=name,
        provider_type="local",
        enabled=True,
        endpoint="http://127.0.0.1:3000",
        model_name="qwen3.5:9b",
        timeout_sec=5,
        priority=provider_id,
        capabilities=["proposal_explanation"],
        allowed_tools=[],
        capability_tools={},
        discovered_tools=[],
        discovered_models=["previous-model"],
        health="UNKNOWN",
    )


def test_periodic_health_check_isolates_failures_and_preserves_discovery(
    session,
    make_settings,
    monkeypatch,
):
    mcp = _mcp_provider(1, "Healthy MCP")
    local = _local_provider(2, "Unavailable Local")
    session.add_all([mcp, local])
    session.flush()

    async def fake_mcp_inspect(config, settings):
        return 11.5, [{"name": "search_news", "description": "Trusted search"}]

    def fake_local_inspect(config, settings):
        raise ConnectionError("Open WebUI offline")

    monkeypatch.setattr(provider_health, "inspect_mcp_provider", fake_mcp_inspect)
    monkeypatch.setattr(
        provider_health,
        "inspect_open_webui_provider",
        fake_local_inspect,
    )

    summary = asyncio.run(
        provider_health.refresh_provider_health(
            session,
            make_settings(),
            force=True,
        )
    )

    assert summary["checked"] == 2
    assert summary["healthy"] == 1
    assert summary["unhealthy"] == 1
    assert mcp.health == "HEALTHY"
    assert mcp.discovered_tools[0]["name"] == "search_news"
    assert local.health == "UNHEALTHY"
    assert local.discovered_models == ["previous-model"]
    assert local.last_error == "Open WebUI offline"


def test_periodic_health_check_skips_fresh_and_disabled_providers(
    session,
    make_settings,
    monkeypatch,
):
    fresh = _mcp_provider(1, "Fresh")
    fresh.last_checked_at = utcnow()
    disabled = _mcp_provider(2, "Disabled")
    disabled.enabled = False
    session.add_all([fresh, disabled])
    session.flush()
    calls = 0

    async def fake_mcp_inspect(config, settings):
        nonlocal calls
        calls += 1
        return 1.0, []

    monkeypatch.setattr(provider_health, "inspect_mcp_provider", fake_mcp_inspect)

    summary = asyncio.run(
        provider_health.refresh_provider_health(
            session,
            make_settings(
                analysis_provider_health_check_interval_seconds=300,
            ),
        )
    )

    assert summary["eligible"] == 1
    assert summary["due"] == 0
    assert summary["checked"] == 0
    assert summary["skipped"] == 1
    assert calls == 0


def test_periodic_health_check_can_be_disabled(session, make_settings):
    session.add(_mcp_provider(1, "Disabled periodic checks"))
    session.flush()

    summary = asyncio.run(
        provider_health.refresh_provider_health(
            session,
            make_settings(analysis_provider_health_checks_enabled=False),
        )
    )

    assert summary["periodic_enabled"] is False
    assert summary["checked"] == 0
    assert summary["skipped"] == 1


def test_single_health_check_records_unexpected_errors(
    session,
    make_settings,
    monkeypatch,
):
    row = _mcp_provider(1, "Broken MCP")
    session.add(row)
    session.flush()

    async def fake_mcp_inspect(config, settings):
        raise RuntimeError("unexpected client failure")

    monkeypatch.setattr(provider_health, "inspect_mcp_provider", fake_mcp_inspect)

    result = asyncio.run(
        provider_health.check_provider_health(
            row,
            AnalysisProviderRepository(session),
            make_settings(),
        )
    )

    assert result.health == "UNHEALTHY"
    assert result.error == "unexpected client failure"
    assert row.last_checked_at is not None
