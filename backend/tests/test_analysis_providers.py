from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.ai.open_webui import (
    OpenWebUIError,
    OpenWebUIProvider,
    inspect_open_webui_provider,
    validate_open_webui_endpoint,
)
from app.core.config import get_settings
from app.main import create_app
from app.persistence.db import get_db
from app.persistence.entities import AnalysisProviderRow, AuditLogRow
from app.providers import health as provider_health
from app.providers.mcp_client import ProviderConnectionError, validate_mcp_endpoint
from app.providers.models import AnalysisProviderConfig
from app.providers.routing import capability_routes


def _payload(**overrides) -> dict:
    payload = {
        "display_name": "Local news MCP",
        "provider_type": "mcp",
        "enabled": True,
        "transport": "streamable_http",
        "endpoint": "http://127.0.0.1:9000/mcp",
        "secret_ref": "MCP_PROVIDER_NEWS_TOKEN",
        "timeout_sec": 5,
        "priority": 10,
        "capabilities": ["news_search", "economic_calendar"],
        "allowed_tools": ["search_news"],
        "capability_tools": {
            "news_search": "search_news",
            "economic_calendar": "search_news",
        },
    }
    payload.update(overrides)
    return payload


def test_provider_config_requires_safe_secret_reference():
    with pytest.raises(ValueError, match="MCP_PROVIDER"):
        AnalysisProviderConfig.model_validate(
            _payload(secret_ref="OPENAI_API_KEY")
        )


def test_local_provider_requires_endpoint_and_model():
    with pytest.raises(ValueError, match="model name"):
        AnalysisProviderConfig.model_validate(
            _payload(
                display_name="Local model",
                provider_type="local",
                transport=None,
                endpoint="http://127.0.0.1:3000",
                model_name=None,
                secret_ref="ANALYSIS_PROVIDER_OPEN_WEBUI_KEY",
                capability_tools={},
            )
        )


def test_enabled_openai_provider_requires_secret_reference():
    with pytest.raises(ValueError, match="secret reference"):
        AnalysisProviderConfig.model_validate(
            _payload(
                display_name="OpenAI fallback",
                provider_type="openai",
                transport=None,
                endpoint="https://api.openai.com/v1",
                model_name="gpt-5.5",
                secret_ref=None,
                capabilities=["proposal_explanation"],
                allowed_tools=[],
                capability_tools={},
            )
        )


def test_endpoint_host_allowlist_and_https(make_settings):
    settings = make_settings(mcp_allowed_hosts="mcp.example.com")

    with pytest.raises(ProviderConnectionError, match="must use HTTPS"):
        validate_mcp_endpoint("http://mcp.example.com/mcp", settings)
    with pytest.raises(ProviderConnectionError, match="MCP_ALLOWED_HOSTS"):
        validate_mcp_endpoint("https://other.example.com/mcp", settings)

    validate_mcp_endpoint("https://mcp.example.com/mcp", settings)


def test_open_webui_endpoint_host_allowlist_and_https(make_settings):
    settings = make_settings(analysis_provider_allowed_hosts="ai.example.com")
    with pytest.raises(OpenWebUIError, match="must use HTTPS"):
        validate_open_webui_endpoint("http://ai.example.com", settings)
    with pytest.raises(OpenWebUIError, match="ANALYSIS_PROVIDER_ALLOWED_HOSTS"):
        validate_open_webui_endpoint("https://other.example.com", settings)
    validate_open_webui_endpoint("https://ai.example.com", settings)


def test_open_webui_inspection_and_analysis_enforce_config(make_settings, monkeypatch):
    requests: list[tuple[str, str, dict | None]] = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url):
            requests.append(("GET", url, None))
            return FakeResponse({"data": [{"id": "qwen3.5:9b"}]})

        def post(self, url, json):
            requests.append(("POST", url, json))
            return FakeResponse(
                {"choices": [{"message": {"content": "Advisory summary"}}]}
            )

    monkeypatch.setattr("app.ai.open_webui.httpx.Client", FakeClient)
    monkeypatch.setenv("ANALYSIS_PROVIDER_OPEN_WEBUI_KEY", "secret")
    settings = make_settings()
    config = AnalysisProviderConfig.model_validate(
        _payload(
            display_name="Local Open WebUI",
            provider_type="local",
            transport=None,
            endpoint="http://127.0.0.1:3000",
            model_name="qwen3.5:9b",
            web_search_enabled=True,
            secret_ref="ANALYSIS_PROVIDER_OPEN_WEBUI_KEY",
            allowed_tools=["server:mcp:trusted-search"],
            capabilities=["proposal_explanation"],
            capability_tools={},
        )
    )

    _, models = inspect_open_webui_provider(config, settings)
    result = OpenWebUIProvider(config, settings).analyze("Explain", {"symbol": "XAUUSD"})

    assert models == ["qwen3.5:9b"]
    assert result["summary"] == "Advisory summary"
    payload = requests[-1][2]
    assert payload["features"] == {"web_search": True}
    assert payload["tool_ids"] == ["server:mcp:trusted-search"]
    assert requests[0][1].endswith("/api/models")
    assert requests[-1][1].endswith("/api/chat/completions")


def test_capability_routes_skip_disabled_and_unhealthy():
    healthy = AnalysisProviderRow(
        id=1,
        display_name="Healthy",
        provider_type="mcp",
        enabled=True,
        priority=20,
        capabilities=["news_search"],
        health="HEALTHY",
    )
    higher_priority_but_unhealthy = AnalysisProviderRow(
        id=2,
        display_name="Unhealthy",
        provider_type="mcp",
        enabled=True,
        priority=1,
        capabilities=["news_search"],
        health="UNHEALTHY",
    )

    routes = capability_routes([higher_priority_but_unhealthy, healthy])

    assert [row.display_name for row in routes["news_search"]] == ["Healthy"]


def test_provider_api_crud_test_discovery_and_audit(
    session,
    make_settings,
    monkeypatch,
):
    app = create_app()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: make_settings()

    async def fake_inspect(config, settings):
        return 12.5, [
            {
                "name": "search_news",
                "title": "Search News",
                "description": "Searches trusted news sources",
            }
        ]

    monkeypatch.setattr(provider_health, "inspect_mcp_provider", fake_inspect)
    monkeypatch.setenv("MCP_PROVIDER_NEWS_TOKEN", "never-return-this-value")

    with TestClient(app) as client:
        created = client.post("/api/settings/analysis-providers", json=_payload())
        assert created.status_code == 201
        provider = created.json()
        assert provider["health"] == "UNKNOWN"
        assert provider["secret_configured"] is True
        assert "never-return-this-value" not in created.text

        tested = client.post(
            f"/api/settings/analysis-providers/{provider['id']}/test"
        )
        assert tested.status_code == 200
        tested_provider = tested.json()
        assert tested_provider["health"] == "HEALTHY"
        assert tested_provider["latency_ms"] == 12.5
        assert tested_provider["discovered_tools"][0]["name"] == "search_news"

        routing = client.get("/api/settings/analysis-providers/routing")
        assert routing.status_code == 200
        assert routing.json()["news_search"][0]["id"] == provider["id"]

        batch = client.post("/api/settings/analysis-providers/health-check")
        assert batch.status_code == 200
        assert batch.json()["checked"] == 1
        assert batch.json()["healthy"] == 1

        deleted = client.delete(
            f"/api/settings/analysis-providers/{provider['id']}"
        )
        assert deleted.status_code == 204

    events = [row.event for row in session.query(AuditLogRow).all()]
    assert events == [
        "provider.configuration_created",
        "provider.connection_tested",
        "provider.health_batch_tested",
        "provider.configuration_deleted",
    ]
    assert all(
        "never-return-this-value" not in str(row.payload)
        for row in session.query(AuditLogRow).all()
    )
    assert os.getenv("MCP_PROVIDER_NEWS_TOKEN") == "never-return-this-value"


def test_local_provider_api_connection_test(
    session,
    make_settings,
    monkeypatch,
):
    app = create_app()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: make_settings()
    monkeypatch.setattr(
        provider_health,
        "inspect_open_webui_provider",
        lambda config, settings: (8.2, ["qwen3.5:9b"]),
    )
    payload = _payload(
        display_name="Local Open WebUI",
        provider_type="local",
        transport=None,
        endpoint="http://127.0.0.1:3000",
        model_name="qwen3.5:9b",
        web_search_enabled=True,
        secret_ref=None,
        allowed_tools=[],
        capabilities=["proposal_explanation"],
        capability_tools={},
    )

    with TestClient(app) as client:
        created = client.post("/api/settings/analysis-providers", json=payload)
        assert created.status_code == 201
        tested = client.post(
            f"/api/settings/analysis-providers/{created.json()['id']}/test"
        )

    assert tested.status_code == 200
    result = tested.json()
    assert result["health"] == "HEALTHY"
    assert result["model_name"] == "qwen3.5:9b"
    assert result["web_search_enabled"] is True
    assert result["discovered_models"] == ["qwen3.5:9b"]
