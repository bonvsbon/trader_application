"""Restricted OpenAI Responses API adapter for advisory analysis."""

from __future__ import annotations

import json
import os
import time
from urllib.parse import quote, urlparse

import httpx

from app.core.config import Settings
from app.providers.models import AnalysisProviderConfig


class OpenAIProviderError(RuntimeError):
    pass


def validate_openai_endpoint(endpoint: str, settings: Settings) -> None:
    parsed = urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    if host not in set(settings.openai_provider_allowed_host_list):
        raise OpenAIProviderError(
            f"OpenAI provider host {host!r} is not in OPENAI_PROVIDER_ALLOWED_HOSTS"
        )
    if parsed.scheme != "https":
        raise OpenAIProviderError("OpenAI provider endpoints must use HTTPS")


def _headers(config: AnalysisProviderConfig) -> dict[str, str]:
    if not config.secret_ref:
        raise OpenAIProviderError("OpenAI provider requires a secret reference")
    secret = os.getenv(config.secret_ref, "")
    if not secret:
        raise OpenAIProviderError(
            f"Secret reference {config.secret_ref} is not configured"
        )
    return {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
    }


def _response_text(payload: object) -> str:
    if not isinstance(payload, dict):
        raise OpenAIProviderError("OpenAI returned an invalid response")
    helper_text = payload.get("output_text")
    if isinstance(helper_text, str) and helper_text.strip():
        return helper_text.strip()

    parts: list[str] = []
    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if (
                    isinstance(part, dict)
                    and part.get("type") == "output_text"
                    and isinstance(part.get("text"), str)
                ):
                    parts.append(part["text"])
    text = "\n".join(parts).strip()
    if not text:
        raise OpenAIProviderError("OpenAI returned an empty text response")
    return text


def inspect_openai_provider(
    config: AnalysisProviderConfig,
    settings: Settings,
) -> tuple[float, list[str]]:
    if (
        config.provider_type != "openai"
        or not config.endpoint
        or not config.model_name
    ):
        raise OpenAIProviderError("Provider is not a complete OpenAI configuration")
    validate_openai_endpoint(config.endpoint, settings)
    started = time.perf_counter()
    try:
        with httpx.Client(
            headers=_headers(config),
            timeout=config.timeout_sec,
            follow_redirects=False,
        ) as client:
            response = client.get(
                f"{config.endpoint}/models/{quote(config.model_name, safe='')}"
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OpenAIProviderError(str(exc) or type(exc).__name__) from exc
    model_id = payload.get("id") if isinstance(payload, dict) else None
    if model_id != config.model_name:
        raise OpenAIProviderError(
            "OpenAI model lookup did not return the configured model"
        )
    return round((time.perf_counter() - started) * 1000, 1), [model_id]


class OpenAIProvider:
    """Advisory-only cloud provider with no execution or MT5 dependency."""

    name = "openai"

    def __init__(self, config: AnalysisProviderConfig, settings: Settings) -> None:
        if not config.enabled:
            raise OpenAIProviderError("OpenAI provider is disabled")
        if (
            config.provider_type != "openai"
            or not config.endpoint
            or not config.model_name
        ):
            raise OpenAIProviderError("Provider is not a complete OpenAI configuration")
        validate_openai_endpoint(config.endpoint, settings)
        self.config = config
        self.settings = settings

    def analyze(self, prompt: str, context: dict) -> dict:
        payload: dict = {
            "model": self.config.model_name,
            "instructions": (
                "You are an advisory trading analyst. Never place orders, change "
                "risk rules, claim that an order is approved, or invent live market "
                "facts. Clearly distinguish supplied context from inference."
            ),
            "input": (
                f"{prompt}\n\nContext JSON:\n"
                f"{json.dumps(context, ensure_ascii=False, default=str)}"
            ),
            "store": False,
        }
        if self.config.web_search_enabled:
            payload["tools"] = [{"type": "web_search"}]

        try:
            with httpx.Client(
                headers=_headers(self.config),
                timeout=self.config.timeout_sec,
                follow_redirects=False,
            ) as client:
                response = client.post(
                    f"{self.config.endpoint}/responses",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OpenAIProviderError(str(exc) or type(exc).__name__) from exc

        content = _response_text(data)
        if len(content) > self.settings.analysis_provider_max_response_chars:
            raise OpenAIProviderError(
                "OpenAI response exceeded the configured size limit"
            )
        return {
            "summary": content,
            "confidence": 0.0,
            "provider": self.name,
            "model": self.config.model_name,
            "web_search_enabled": self.config.web_search_enabled,
        }
