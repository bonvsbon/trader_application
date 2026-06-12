"""Runtime analysis chokepoint with failover and sanitized provenance."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from uuid import uuid4

from sqlalchemy.orm import Session

from app.ai.open_webui import OpenWebUIProvider
from app.ai.openai_provider import OpenAIProvider
from app.core.config import Settings, get_settings
from app.persistence.repositories import (
    AnalysisProviderRepository,
    AnalysisSnapshotRepository,
)
from app.providers.health import provider_config_from_row
from app.providers.mcp_client import call_mcp_tool
from app.providers.models import ANALYSIS_CAPABILITIES
from app.providers.routing import capability_routes


@dataclass
class AnalysisAttempt:
    provider_id: int | None
    provider_name: str | None
    provider_type: str | None
    success: bool
    latency_ms: float | None = None
    model_or_tool: str | None = None
    error: str | None = None


@dataclass
class AnalysisResult:
    capability: str
    correlation_id: str
    summary: str | None
    confidence: float = 0.0
    provider_id: int | None = None
    provider_name: str | None = None
    provider_type: str | None = None
    model_or_tool: str | None = None
    attempts: list[AnalysisAttempt] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return bool(self.summary)


_REDACT_KEYS = {
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "api_secret",
    "login",
}
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_ -]?key|api[_ -]?secret|password|token|secret)"
    r"\s*[:=]\s*[\"']?[^\s,\"'}]+"
)
_ENV_SECRET_ASSIGNMENT_RE = re.compile(
    r"\b([A-Z][A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD))"
    r"\s*[:=]\s*[\"']?[^\s,\"'}]+"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower().replace("-", "_").replace(" ", "_")
    return (
        normalized in _REDACT_KEYS
        or normalized.endswith(("_api_key", "_api_secret", "_password", "_token"))
        or normalized.endswith(("_secret", "_key", "_login"))
    )


def _sanitize(value, *, depth: int = 0):
    if depth > 4:
        return "[truncated]"
    if isinstance(value, dict):
        return {
            str(key)[:100]: (
                "[redacted]"
                if _is_sensitive_key(key)
                else _sanitize(item, depth=depth + 1)
            )
            for key, item in list(value.items())[:50]
        }
    if isinstance(value, list):
        return [_sanitize(item, depth=depth + 1) for item in value[:50]]
    if isinstance(value, str):
        sanitized = _SENSITIVE_ASSIGNMENT_RE.sub(r"\1=[redacted]", value)
        sanitized = _ENV_SECRET_ASSIGNMENT_RE.sub(r"\1=[redacted]", sanitized)
        sanitized = _BEARER_RE.sub("Bearer [redacted]", sanitized)
        return sanitized[:2000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:500]


class AnalysisService:
    """The only runtime entry point for AI/MCP analysis."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.providers = AnalysisProviderRepository(session)
        self.snapshots = AnalysisSnapshotRepository(session)

    def analyze(self, capability: str, prompt: str, context: dict) -> AnalysisResult:
        if capability not in ANALYSIS_CAPABILITIES:
            raise ValueError(f"Unsupported analysis capability: {capability}")
        correlation_id = uuid4().hex
        sanitized_input = {
            "prompt": _sanitize(prompt),
            "context": _sanitize(context),
        }
        result = AnalysisResult(
            capability=capability,
            correlation_id=correlation_id,
            summary=None,
        )
        chain = capability_routes(self.providers.list_all())[capability]
        if not chain:
            self.snapshots.record(
                correlation_id=correlation_id,
                capability=capability,
                provider_id=None,
                provider_type=None,
                provider_name=None,
                model_or_tool=None,
                success=False,
                latency_ms=None,
                input_summary=sanitized_input,
                output_summary=None,
                error="No enabled healthy provider for capability",
            )
            return result

        for row in chain:
            started = time.perf_counter()
            config = provider_config_from_row(row)
            model_or_tool = config.model_name
            try:
                if config.provider_type == "local":
                    provider_result = OpenWebUIProvider(config, self.settings).analyze(
                        prompt,
                        context,
                    )
                    summary = provider_result["summary"]
                    confidence = float(provider_result.get("confidence", 0.0))
                    latency_ms = round((time.perf_counter() - started) * 1000, 1)
                elif config.provider_type == "openai":
                    provider_result = OpenAIProvider(config, self.settings).analyze(
                        prompt,
                        context,
                    )
                    summary = provider_result["summary"]
                    confidence = float(provider_result.get("confidence", 0.0))
                    latency_ms = round((time.perf_counter() - started) * 1000, 1)
                elif config.provider_type == "mcp":
                    tool_name = config.capability_tools.get(capability)
                    if not tool_name:
                        raise ValueError(
                            f"No MCP tool mapping configured for {capability}"
                        )
                    model_or_tool = tool_name
                    latency_ms, summary = asyncio.run(
                        call_mcp_tool(
                            config,
                            self.settings,
                            tool_name=tool_name,
                            arguments={"query": prompt, "context": _sanitize(context)},
                        )
                    )
                    confidence = 0.0
                else:
                    raise ValueError(
                        f"{config.provider_type} runtime adapter is not implemented"
                    )

                self.snapshots.record(
                    correlation_id=correlation_id,
                    capability=capability,
                    provider_id=row.id,
                    provider_type=row.provider_type,
                    provider_name=row.display_name,
                    model_or_tool=model_or_tool,
                    success=True,
                    latency_ms=latency_ms,
                    input_summary=sanitized_input,
                    output_summary=_sanitize(summary),
                    error=None,
                )
                result.summary = summary
                result.confidence = confidence
                result.provider_id = row.id
                result.provider_name = row.display_name
                result.provider_type = row.provider_type
                result.model_or_tool = model_or_tool
                result.attempts.append(
                    AnalysisAttempt(
                        provider_id=row.id,
                        provider_name=row.display_name,
                        provider_type=row.provider_type,
                        success=True,
                        latency_ms=latency_ms,
                        model_or_tool=model_or_tool,
                    )
                )
                return result
            except Exception as exc:
                latency_ms = round((time.perf_counter() - started) * 1000, 1)
                error = (str(exc) or type(exc).__name__)[:2000]
                self.snapshots.record(
                    correlation_id=correlation_id,
                    capability=capability,
                    provider_id=row.id,
                    provider_type=row.provider_type,
                    provider_name=row.display_name,
                    model_or_tool=model_or_tool,
                    success=False,
                    latency_ms=latency_ms,
                    input_summary=sanitized_input,
                    output_summary=None,
                    error=error,
                )
                result.attempts.append(
                    AnalysisAttempt(
                        provider_id=row.id,
                        provider_name=row.display_name,
                        provider_type=row.provider_type,
                        success=False,
                        latency_ms=latency_ms,
                        model_or_tool=model_or_tool,
                        error=error,
                    )
                )
        return result
