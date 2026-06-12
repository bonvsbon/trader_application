"""Shared manual and periodic health checks for analysis providers."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai.open_webui import inspect_open_webui_provider
from app.ai.openai_provider import inspect_openai_provider
from app.core.config import Settings
from app.persistence.entities import AnalysisProviderRow, utcnow
from app.persistence.repositories import AnalysisProviderRepository
from app.providers.mcp_client import ProviderConnectionError, inspect_mcp_provider
from app.providers.models import AnalysisProviderConfig


@dataclass(frozen=True)
class ProviderHealthResult:
    provider_id: int
    display_name: str
    provider_type: str
    health: str
    latency_ms: float | None
    discovered_tool_names: list[str]
    discovered_models: list[str]
    error: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def provider_config_from_row(row: AnalysisProviderRow) -> AnalysisProviderConfig:
    return AnalysisProviderConfig.model_validate(
        {
            field: getattr(row, field)
            for field in AnalysisProviderConfig.model_fields
        }
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def provider_health_check_due(
    row: AnalysisProviderRow,
    *,
    interval_seconds: int,
    now: datetime | None = None,
) -> bool:
    if not row.enabled:
        return False
    if row.last_checked_at is None:
        return True
    checked_at = _aware(row.last_checked_at)
    current = _aware(now or utcnow())
    return (current - checked_at).total_seconds() >= interval_seconds


async def check_provider_health(
    row: AnalysisProviderRow,
    repository: AnalysisProviderRepository,
    settings: Settings,
) -> ProviderHealthResult:
    config = provider_config_from_row(row)
    latency_ms: float | None = None
    tools = list(row.discovered_tools or [])
    models = list(row.discovered_models or [])
    error: str | None = None
    health = "UNHEALTHY"

    try:
        if config.provider_type == "mcp":
            latency_ms, tools = await inspect_mcp_provider(config, settings)
        elif config.provider_type == "local":
            latency_ms, models = await asyncio.to_thread(
                inspect_open_webui_provider,
                config,
                settings,
            )
        elif config.provider_type == "openai":
            latency_ms, models = await asyncio.to_thread(
                inspect_openai_provider,
                config,
                settings,
            )
        else:
            raise ProviderConnectionError(
                f"{config.provider_type} adapter is not implemented yet"
            )
        health = "HEALTHY"
    except Exception as exc:
        error = (str(exc) or type(exc).__name__)[:2000]

    repository.record_health(
        row,
        health=health,
        latency_ms=latency_ms,
        discovered_tools=tools,
        discovered_models=models,
        error=error,
    )
    return ProviderHealthResult(
        provider_id=row.id,
        display_name=row.display_name,
        provider_type=row.provider_type,
        health=health,
        latency_ms=latency_ms,
        discovered_tool_names=[
            tool["name"]
            for tool in tools
            if isinstance(tool, dict) and isinstance(tool.get("name"), str)
        ],
        discovered_models=models,
        error=error,
    )


async def refresh_provider_health(
    session: Session,
    settings: Settings,
    *,
    force: bool = False,
) -> dict:
    repository = AnalysisProviderRepository(session)
    enabled_rows = [row for row in repository.list_all() if row.enabled]
    if not force and not settings.analysis_provider_health_checks_enabled:
        return {
            "periodic_enabled": False,
            "interval_seconds": settings.analysis_provider_health_check_interval_seconds,
            "eligible": len(enabled_rows),
            "due": 0,
            "checked": 0,
            "healthy": 0,
            "unhealthy": 0,
            "skipped": len(enabled_rows),
            "results": [],
        }

    due_rows = [
        row
        for row in enabled_rows
        if force
        or provider_health_check_due(
            row,
            interval_seconds=settings.analysis_provider_health_check_interval_seconds,
        )
    ]
    selected = due_rows[: settings.analysis_provider_health_check_batch_size]
    results = [
        await check_provider_health(row, repository, settings)
        for row in selected
    ]
    return {
        "periodic_enabled": settings.analysis_provider_health_checks_enabled,
        "interval_seconds": settings.analysis_provider_health_check_interval_seconds,
        "eligible": len(enabled_rows),
        "due": len(due_rows),
        "checked": len(results),
        "healthy": sum(result.health == "HEALTHY" for result in results),
        "unhealthy": sum(result.health == "UNHEALTHY" for result in results),
        "skipped": len(enabled_rows) - len(results),
        "results": [result.to_dict() for result in results],
    }
