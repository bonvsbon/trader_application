"""Economic-calendar providers and fail-safe mock adapter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.ai.service import AnalysisService
from app.core.config import Settings
from app.domain.models import NewsRisk
from app.news.official_us import OfficialUsNewsProvider


class MockNewsProvider:
    name = "mock"

    def news_risk(self, symbol: str) -> NewsRisk:
        return NewsRisk(
            has_high_impact_within_window=False,
            score=0.0,
            summary="Live news data unavailable (mock provider)",
            provider=self.name,
            is_live=False,
        )


class EconomicCalendarEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    currency: str = Field(min_length=3, max_length=3)
    impact: Literal["low", "medium", "high"]
    starts_at: datetime


class EconomicCalendarPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    events: list[EconomicCalendarEvent] = Field(max_length=500)


class RoutedMcpNewsProvider:
    """Risk-critical calendar adapter restricted to healthy routed MCP tools."""

    name = "routed_mcp"

    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        mt5_account_id: int = 1,
    ) -> None:
        self.analysis = AnalysisService(
            session,
            settings,
            mt5_account_id=mt5_account_id,
        )
        self.block_window_minutes = settings.risk_news_block_window_min
        self.max_age_minutes = settings.news_max_age_minutes

    def news_risk(self, symbol: str) -> NewsRisk:
        now = datetime.now(timezone.utc)
        currencies = _symbol_currencies(symbol)
        result = self.analysis.analyze(
            "economic_calendar",
            (
                "Return only JSON with this exact schema: "
                '{"generated_at":"ISO-8601 UTC","events":[{"title":"...",'
                '"currency":"USD","impact":"low|medium|high",'
                '"starts_at":"ISO-8601 UTC"}]}. '
                "Do not add markdown or commentary."
            ),
            {
                "symbol": symbol.upper(),
                "currencies": sorted(currencies),
                "window_start": (
                    now.replace(microsecond=0)
                ).isoformat(),
                "window_minutes_each_side": self.block_window_minutes,
            },
            allowed_provider_types={"mcp"},
        )
        if not result.available or not result.summary:
            raise RuntimeError("No healthy MCP economic-calendar route is available")

        payload = EconomicCalendarPayload.model_validate(json.loads(result.summary))
        generated_at = _aware(payload.generated_at)
        age_minutes = (now - generated_at).total_seconds() / 60.0
        if age_minutes < -5:
            raise RuntimeError("Economic-calendar timestamp is in the future")
        if age_minutes > self.max_age_minutes:
            raise RuntimeError(
                f"Economic-calendar data is stale ({age_minutes:.0f} min old)"
            )

        relevant = [
            event
            for event in payload.events
            if event.currency.upper() in currencies and event.impact == "high"
        ]
        nearby = [
            event
            for event in relevant
            if abs((_aware(event.starts_at) - now).total_seconds() / 60.0)
            <= self.block_window_minutes
        ]
        if not nearby:
            return NewsRisk(
                has_high_impact_within_window=False,
                score=0.0,
                summary=(
                    f"Calendar clear for {','.join(sorted(currencies))}; "
                    f"generated {age_minutes:.1f} min ago"
                ),
                provider=self.name,
                is_live=True,
            )

        nearest = min(
            nearby,
            key=lambda event: abs((_aware(event.starts_at) - now).total_seconds()),
        )
        minutes = (_aware(nearest.starts_at) - now).total_seconds() / 60.0
        return NewsRisk(
            has_high_impact_within_window=True,
            minutes_to_next_high_impact=minutes,
            score=1.0,
            summary=f"{nearest.currency.upper()} high impact: {nearest.title}",
            provider=self.name,
            is_live=True,
        )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _symbol_currencies(symbol: str) -> set[str]:
    normalized = symbol.upper()
    if normalized.startswith(("XAU", "XAG")):
        return {"USD"}
    currencies = {
        normalized[index : index + 3]
        for index in (0, 3)
        if len(normalized) >= index + 3
    }
    return currencies or {"USD"}


def create_news_provider(
    settings: Settings | None = None,
    session: Session | None = None,
    *,
    mt5_account_id: int = 1,
):
    configured = settings or Settings()
    if configured.news_provider == "mock":
        return MockNewsProvider()
    if configured.news_provider == "routed_mcp":
        if session is None:
            raise ValueError("Database session is required for NEWS_PROVIDER=routed_mcp")
        return RoutedMcpNewsProvider(
            session,
            configured,
            mt5_account_id=mt5_account_id,
        )
    if configured.news_provider == "official_us":
        return OfficialUsNewsProvider(configured)
    raise ValueError(f"Unsupported news provider: {configured.news_provider}")


def upcoming_news_events(
    provider,
    symbol: str,
    *,
    limit: int = 8,
) -> list[dict]:
    loader = getattr(provider, "upcoming_events", None)
    if not callable(loader):
        return []
    try:
        return loader(symbol, limit=limit)
    except Exception:
        # The risk snapshot already fails closed when its source is unavailable.
        return []
