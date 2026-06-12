"""Strategy port + Phase 1 placeholder.

The real XAUUSD D40/D20 (TP 2R, risk 1%) preset is implemented behind this port
in Phase 2. A strategy only *proposes*; proposals still go through the order
chokepoint and Risk Engine like any other order.
"""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.domain.models import StrategyPresetConfig, SymbolQuote


def default_strategy_config(settings: Settings | None = None) -> StrategyPresetConfig:
    settings = settings or get_settings()
    return StrategyPresetConfig(
        enabled=settings.strategy_xauusd_enabled,
        d40_value=settings.strategy_d40_value,
        d20_value=settings.strategy_d20_value,
        reward_risk_ratio=settings.strategy_reward_risk_ratio,
        risk_pct=settings.strategy_risk_pct,
        signal_definition_confirmed=settings.strategy_signal_definition_confirmed,
    )


class NullStrategy:
    """No-op strategy used in Phase 1 (no automatic signals)."""

    name = "null"

    def evaluate(self, symbol: str, quote: SymbolQuote | None) -> dict:
        return {"signal": "none", "reason": "Strategy engine not enabled in Phase 1"}
