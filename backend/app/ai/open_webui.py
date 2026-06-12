"""Restricted Open WebUI adapter for local models served by Ollama."""

from __future__ import annotations

import json
import os
import time
from urllib.parse import urlparse

import httpx

from app.core.config import Settings
from app.providers.models import AnalysisProviderConfig


class OpenWebUIError(RuntimeError):
    pass


def validate_open_webui_endpoint(endpoint: str, settings: Settings) -> None:
    parsed = urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    if host not in set(settings.analysis_provider_allowed_host_list):
        raise OpenWebUIError(
            f"Analysis provider host {host!r} is not in ANALYSIS_PROVIDER_ALLOWED_HOSTS"
        )
    if parsed.scheme != "https" and host not in {"localhost", "127.0.0.1", "::1"}:
        raise OpenWebUIError("Remote analysis provider endpoints must use HTTPS")


def _headers(config: AnalysisProviderConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.secret_ref:
        secret = os.getenv(config.secret_ref, "")
        if not secret:
            raise OpenWebUIError(
                f"Secret reference {config.secret_ref} is not configured"
            )
        headers["Authorization"] = f"Bearer {secret}"
    return headers


def _model_ids(payload: object) -> list[str]:
    if isinstance(payload, dict):
        values = payload.get("data", payload.get("models", []))
    else:
        values = payload
    if not isinstance(values, list):
        raise OpenWebUIError("Open WebUI returned an invalid model list")
    model_ids: list[str] = []
    for item in values:
        if isinstance(item, str):
            model_ids.append(item)
        elif isinstance(item, dict):
            model_id = item.get("id") or item.get("name")
            if isinstance(model_id, str) and model_id:
                model_ids.append(model_id)
    return list(dict.fromkeys(model_ids))


def inspect_open_webui_provider(
    config: AnalysisProviderConfig,
    settings: Settings,
) -> tuple[float, list[str]]:
    if config.provider_type != "local" or not config.endpoint or not config.model_name:
        raise OpenWebUIError("Provider is not a complete Local/Open WebUI configuration")
    validate_open_webui_endpoint(config.endpoint, settings)
    started = time.perf_counter()
    try:
        with httpx.Client(
            headers=_headers(config),
            timeout=config.timeout_sec,
            follow_redirects=False,
        ) as client:
            response = client.get(f"{config.endpoint}/api/models")
            response.raise_for_status()
            models = _model_ids(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        raise OpenWebUIError(str(exc) or type(exc).__name__) from exc
    if config.model_name not in models:
        raise OpenWebUIError(
            f"Configured model {config.model_name!r} was not returned by Open WebUI"
        )
    return round((time.perf_counter() - started) * 1000, 1), models


class OpenWebUIProvider:
    """Advisory-only AI provider. It has no dependency on execution or MT5."""

    name = "open_webui"

    def __init__(self, config: AnalysisProviderConfig, settings: Settings) -> None:
        if not config.enabled:
            raise OpenWebUIError("Open WebUI provider is disabled")
        if config.provider_type != "local" or not config.endpoint or not config.model_name:
            raise OpenWebUIError("Provider is not a complete Local/Open WebUI configuration")
        validate_open_webui_endpoint(config.endpoint, settings)
        self.config = config
        self.settings = settings

    def analyze(self, prompt: str, context: dict) -> dict:
        payload: dict = {
            "model": self.config.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an advisory trading analyst. Never place orders, "
                        "change risk rules, or claim that an order is approved."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{prompt}\n\nContext JSON:\n"
                        f"{json.dumps(context, ensure_ascii=False, default=str)}"
                    ),
                },
            ],
            "stream": False,
        }
        if self.config.web_search_enabled:
            payload["features"] = {"web_search": True}
        if self.config.allowed_tools:
            payload["tool_ids"] = self.config.allowed_tools

        try:
            with httpx.Client(
                headers=_headers(self.config),
                timeout=self.config.timeout_sec,
                follow_redirects=False,
            ) as client:
                response = client.post(
                    f"{self.config.endpoint}/api/chat/completions",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OpenWebUIError(str(exc) or type(exc).__name__) from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenWebUIError("Open WebUI returned an invalid chat response") from exc
        if not isinstance(content, str) or not content.strip():
            raise OpenWebUIError("Open WebUI returned an empty analysis")
        content = content.strip()
        if len(content) > self.settings.analysis_provider_max_response_chars:
            raise OpenWebUIError("Open WebUI response exceeded the configured size limit")
        return {
            "summary": content,
            "confidence": 0.0,
            "provider": self.name,
            "model": self.config.model_name,
            "web_search_enabled": self.config.web_search_enabled,
            "tool_ids": list(self.config.allowed_tools),
        }
