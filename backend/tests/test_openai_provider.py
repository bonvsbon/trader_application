from __future__ import annotations

import pytest

from app.ai.openai_provider import (
    OpenAIProvider,
    OpenAIProviderError,
    inspect_openai_provider,
    validate_openai_endpoint,
)
from app.providers.models import AnalysisProviderConfig


def _config(**overrides) -> AnalysisProviderConfig:
    values = {
        "display_name": "OpenAI fallback",
        "provider_type": "openai",
        "enabled": True,
        "transport": None,
        "endpoint": "https://api.openai.com/v1",
        "model_name": "gpt-5.5",
        "web_search_enabled": True,
        "secret_ref": "ANALYSIS_PROVIDER_OPENAI_KEY",
        "timeout_sec": 15,
        "priority": 50,
        "capabilities": ["proposal_explanation"],
        "allowed_tools": [],
        "capability_tools": {},
    }
    values.update(overrides)
    return AnalysisProviderConfig.model_validate(values)


def test_openai_endpoint_requires_https_and_allowlist(make_settings):
    settings = make_settings(openai_provider_allowed_hosts="api.openai.com")

    with pytest.raises(OpenAIProviderError, match="must use HTTPS"):
        validate_openai_endpoint("http://api.openai.com/v1", settings)
    with pytest.raises(OpenAIProviderError, match="OPENAI_PROVIDER_ALLOWED_HOSTS"):
        validate_openai_endpoint("https://other.example.com/v1", settings)

    validate_openai_endpoint("https://api.openai.com/v1", settings)


def test_openai_inspection_and_responses_payload(
    make_settings,
    monkeypatch,
):
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
            assert kwargs["headers"]["Authorization"] == "Bearer test-secret"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url):
            requests.append(("GET", url, None))
            return FakeResponse({"id": "gpt-5.5", "object": "model"})

        def post(self, url, json):
            requests.append(("POST", url, json))
            return FakeResponse(
                {
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "Advisory cloud summary",
                                }
                            ],
                        }
                    ]
                }
            )

    monkeypatch.setattr("app.ai.openai_provider.httpx.Client", FakeClient)
    monkeypatch.setenv("ANALYSIS_PROVIDER_OPENAI_KEY", "test-secret")
    settings = make_settings()
    config = _config()

    _, models = inspect_openai_provider(config, settings)
    result = OpenAIProvider(config, settings).analyze(
        "Explain the proposal",
        {"symbol": "XAUUSD"},
    )

    assert models == ["gpt-5.5"]
    assert result["summary"] == "Advisory cloud summary"
    assert requests[0][1].endswith("/models/gpt-5.5")
    method, url, payload = requests[-1]
    assert method == "POST"
    assert url.endswith("/responses")
    assert payload["model"] == "gpt-5.5"
    assert payload["store"] is False
    assert payload["tools"] == [{"type": "web_search"}]
    assert "XAUUSD" in payload["input"]


def test_openai_provider_requires_environment_secret(
    make_settings,
    monkeypatch,
):
    monkeypatch.delenv("ANALYSIS_PROVIDER_OPENAI_KEY", raising=False)

    with pytest.raises(OpenAIProviderError, match="not configured"):
        OpenAIProvider(_config(), make_settings()).analyze("Explain", {})
