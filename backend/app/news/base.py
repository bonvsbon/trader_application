"""News/volatility provider port + Phase 1 mock.

Phase 2 wires a real economic-calendar provider. The Phase 1 mock returns a
neutral risk (no high-impact event) so the system runs, while keeping the BLOCK
path wired: if a real provider is configured and fails, the order chokepoint
treats the failure as risk-present rather than risk-free.
"""

from __future__ import annotations

from app.core.config import Settings
from app.domain.models import NewsRisk


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


def create_news_provider(settings: Settings | None = None):
    # Only the mock exists in Phase 1; real providers are added in Phase 2.
    return MockNewsProvider()
