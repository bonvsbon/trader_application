"""Volatility/session provider port and fail-safe mock adapter."""

from __future__ import annotations

from app.core.config import Settings
from app.domain.models import VolatilityRisk


class MockVolatilityProvider:
    name = "mock"

    def volatility_risk(self, symbol: str) -> VolatilityRisk:
        return VolatilityRisk(
            abnormal=False,
            score=0.0,
            summary="Live volatility data unavailable (mock provider)",
            provider=self.name,
            is_live=False,
        )


def create_volatility_provider(settings: Settings | None = None):
    # A live adapter will replace this factory branch when configured.
    return MockVolatilityProvider()
