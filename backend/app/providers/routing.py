"""Capability routing over enabled, healthy analysis providers."""

from __future__ import annotations

from app.persistence.entities import AnalysisProviderRow
from app.providers.models import ANALYSIS_CAPABILITIES


def capability_routes(rows: list[AnalysisProviderRow]) -> dict[str, list[AnalysisProviderRow]]:
    routes: dict[str, list[AnalysisProviderRow]] = {
        capability: [] for capability in ANALYSIS_CAPABILITIES
    }
    for row in sorted(rows, key=lambda item: (item.priority, item.id or 0)):
        if not row.enabled or row.health != "HEALTHY":
            continue
        for capability in row.capabilities or []:
            if capability in routes:
                routes[capability].append(row)
    return routes


def select_provider(
    rows: list[AnalysisProviderRow],
    capability: str,
) -> AnalysisProviderRow | None:
    if capability not in ANALYSIS_CAPABILITIES:
        raise ValueError(f"Unsupported analysis capability: {capability}")
    chain = capability_routes(rows)[capability]
    return chain[0] if chain else None
