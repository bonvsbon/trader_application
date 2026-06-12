"""Operator-managed analysis provider registry and MCP health checks."""

from __future__ import annotations

import asyncio
import os
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_operator
from app.core.config import Settings, get_settings
from app.market_data.alpaca import (
    MarketDataConnectionError,
    inspect_alpaca_provider,
)
from app.market_data.base import default_market_data_config
from app.market_data.models import MarketDataConfig
from app.persistence.db import get_db
from app.persistence.entities import AnalysisProviderRow
from app.persistence.repositories import (
    AnalysisProviderRepository,
    AuditRepository,
    MarketDataConfigRepository,
)
from app.providers.health import check_provider_health, refresh_provider_health
from app.providers.models import ANALYSIS_CAPABILITIES, AnalysisProviderConfig
from app.providers.routing import capability_routes

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _provider_dict(row: AnalysisProviderRow) -> dict:
    return {
        "id": row.id,
        "display_name": row.display_name,
        "provider_type": row.provider_type,
        "enabled": row.enabled,
        "transport": row.transport,
        "endpoint": row.endpoint,
        "model_name": row.model_name,
        "web_search_enabled": row.web_search_enabled,
        "secret_ref": row.secret_ref,
        "secret_configured": bool(row.secret_ref and os.getenv(row.secret_ref)),
        "timeout_sec": row.timeout_sec,
        "priority": row.priority,
        "capabilities": row.capabilities or [],
        "allowed_tools": row.allowed_tools or [],
        "capability_tools": row.capability_tools or {},
        "discovered_tools": row.discovered_tools or [],
        "discovered_models": row.discovered_models or [],
        "health": row.health,
        "latency_ms": row.latency_ms,
        "last_checked_at": (
            row.last_checked_at.isoformat() if row.last_checked_at else None
        ),
        "last_error": row.last_error,
        "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _get_or_404(
    repository: AnalysisProviderRepository,
    provider_id: int,
) -> AnalysisProviderRow:
    row = repository.get(provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis provider not found")
    return row


@router.get("/analysis-providers/metadata")
def provider_metadata(
    operator: str = Depends(get_operator),
    settings: Settings = Depends(get_settings),
) -> dict:
    return {
        "provider_types": ["mcp", "claude", "openai", "local"],
        "mcp_transports": ["streamable_http", "sse"],
        "capabilities": list(ANALYSIS_CAPABILITIES),
        "secret_ref_prefix": "ANALYSIS_PROVIDER_",
        "health_checks": {
            "enabled": settings.analysis_provider_health_checks_enabled,
            "interval_seconds": (
                settings.analysis_provider_health_check_interval_seconds
            ),
            "batch_size": settings.analysis_provider_health_check_batch_size,
        },
    }


@router.get("/analysis-providers/routing")
def provider_routing(
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> dict:
    routes = capability_routes(AnalysisProviderRepository(session).list_all())
    return {
        capability: [
            {
                "id": row.id,
                "display_name": row.display_name,
                "provider_type": row.provider_type,
                "priority": row.priority,
            }
            for row in chain
        ]
        for capability, chain in routes.items()
    }


@router.get("/analysis-providers")
def list_analysis_providers(
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> list[dict]:
    return [
        _provider_dict(row)
        for row in AnalysisProviderRepository(session).list_all()
    ]


@router.post("/analysis-providers", status_code=status.HTTP_201_CREATED)
def create_analysis_provider(
    config: AnalysisProviderConfig,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> dict:
    repository = AnalysisProviderRepository(session)
    if repository.get_by_name(config.display_name):
        raise HTTPException(status_code=409, detail="Provider display name already exists")
    row = repository.save(config, updated_by=operator)
    AuditRepository(session).write(
        event="provider.configuration_created",
        payload={
            **config.model_dump(mode="json"),
            "provider_id": row.id,
            "updated_by": operator,
            "stores_plaintext_secret": False,
        },
    )
    return _provider_dict(row)


def _market_data_dict(
    config: MarketDataConfig,
    *,
    source: str,
    row=None,
) -> dict:
    return {
        **config.model_dump(mode="json"),
        "source": source,
        "feed_status": config.feed_status,
        "api_key_configured": bool(
            config.api_key_ref and os.getenv(config.api_key_ref)
        ),
        "api_secret_configured": bool(
            config.api_secret_ref and os.getenv(config.api_secret_ref)
        ),
        "stores_plaintext_secret": False,
        "updated_by": row.updated_by if row else None,
        "updated_at": row.updated_at.isoformat() if row else None,
    }


@router.get("/market-data")
def market_data_configuration(
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
    settings: Settings = Depends(get_settings),
) -> dict:
    repository = MarketDataConfigRepository(session)
    row = repository.get()
    config = repository.get_config() or default_market_data_config(settings)
    return _market_data_dict(
        config,
        source="database" if row else "environment",
        row=row,
    )


@router.put("/market-data")
def update_market_data_configuration(
    config: MarketDataConfig,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> dict:
    row = MarketDataConfigRepository(session).save(config, updated_by=operator)
    AuditRepository(session).write(
        event="market_data.configuration_updated",
        payload={
            **config.model_dump(mode="json"),
            "updated_by": operator,
            "stores_plaintext_secret": False,
        },
    )
    return _market_data_dict(config, source="database", row=row)


@router.post("/market-data/test")
async def test_market_data_configuration(
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
    settings: Settings = Depends(get_settings),
) -> dict:
    repository = MarketDataConfigRepository(session)
    config = repository.get_config() or default_market_data_config(settings)
    started = time.perf_counter()
    try:
        if not config.enabled or config.provider == "disabled":
            raise MarketDataConnectionError("Market-data provider is disabled")
        if config.provider == "alpaca":
            detail = await inspect_alpaca_provider(config, settings)
        else:
            from app.bridge.base import get_configured_bridge

            quote = await asyncio.to_thread(
                get_configured_bridge().quote,
                config.default_symbols[0],
            )
            detail = {
                "provider": "mt5",
                "feed": "broker",
                "feed_status": config.feed_status,
                "symbol": quote.symbol,
            }
        result = {
            "healthy": True,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            **detail,
        }
    except Exception as exc:
        result = {
            "healthy": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "provider": config.provider,
            "feed": config.feed,
            "feed_status": config.feed_status,
            "error": (str(exc) or type(exc).__name__)[:2000],
        }
    AuditRepository(session).write(
        event="market_data.connection_tested",
        payload={**result, "tested_by": operator},
    )
    return result


@router.put("/analysis-providers/{provider_id}")
def update_analysis_provider(
    provider_id: int,
    config: AnalysisProviderConfig,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> dict:
    repository = AnalysisProviderRepository(session)
    row = _get_or_404(repository, provider_id)
    duplicate = repository.get_by_name(config.display_name)
    if duplicate and duplicate.id != provider_id:
        raise HTTPException(status_code=409, detail="Provider display name already exists")
    row = repository.save(config, updated_by=operator, row=row)
    AuditRepository(session).write(
        event="provider.configuration_updated",
        payload={
            **config.model_dump(mode="json"),
            "provider_id": row.id,
            "updated_by": operator,
            "health_reset": True,
            "stores_plaintext_secret": False,
        },
    )
    return _provider_dict(row)


@router.delete("/analysis-providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis_provider(
    provider_id: int,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
) -> None:
    repository = AnalysisProviderRepository(session)
    row = _get_or_404(repository, provider_id)
    AuditRepository(session).write(
        event="provider.configuration_deleted",
        payload={
            "provider_id": row.id,
            "display_name": row.display_name,
            "provider_type": row.provider_type,
            "deleted_by": operator,
        },
    )
    repository.delete(row)


@router.post("/analysis-providers/{provider_id}/test")
async def test_analysis_provider(
    provider_id: int,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
    settings: Settings = Depends(get_settings),
) -> dict:
    repository = AnalysisProviderRepository(session)
    row = _get_or_404(repository, provider_id)
    result = await check_provider_health(row, repository, settings)
    AuditRepository(session).write(
        event="provider.connection_tested",
        payload={
            "provider_id": row.id,
            "display_name": row.display_name,
            **result.to_dict(),
            "tested_by": operator,
        },
    )
    return _provider_dict(row)


@router.post("/analysis-providers/health-check")
async def test_enabled_analysis_providers(
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
    settings: Settings = Depends(get_settings),
) -> dict:
    result = await refresh_provider_health(session, settings, force=True)
    AuditRepository(session).write(
        event="provider.health_batch_tested",
        payload={
            "checked": result["checked"],
            "healthy": result["healthy"],
            "unhealthy": result["unhealthy"],
            "provider_ids": [
                item["provider_id"] for item in result["results"]
            ],
            "tested_by": operator,
        },
    )
    return result
