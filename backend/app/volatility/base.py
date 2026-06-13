"""Volatility/session providers backed by closed MT5 candles."""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import fmean, median

from app.core.config import Settings
from app.domain.models import Candle, VolatilityRisk
from app.domain.ports import MT5BridgePort


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


class Mt5VolatilityProvider:
    """Detect abnormal movement from recent closed candles.

    The current ATR is compared with a preceding median true-range baseline.
    Median keeps one unusually large historical candle from masking a new spike.
    """

    name = "mt5"

    def __init__(self, bridge: MT5BridgePort, settings: Settings) -> None:
        self.bridge = bridge
        self.timeframe = settings.volatility_timeframe.upper()
        self.atr_period = settings.volatility_atr_period
        self.baseline_bars = settings.volatility_baseline_bars
        self.abnormal_ratio = settings.volatility_abnormal_ratio
        self.max_bar_age_minutes = settings.volatility_max_bar_age_minutes

    def volatility_risk(self, symbol: str) -> VolatilityRisk:
        required = self.baseline_bars + self.atr_period + 1
        candles = self.bridge.candles(symbol.upper(), self.timeframe, required)
        if len(candles) < required:
            return self._unavailable(
                f"Insufficient MT5 candles ({len(candles)}/{required})"
            )

        newest = candles[-1].time
        if newest.tzinfo is None:
            newest = newest.replace(tzinfo=timezone.utc)
        age_minutes = max(
            0.0,
            (datetime.now(timezone.utc) - newest).total_seconds() / 60.0,
        )
        session = _utc_session(newest)
        if age_minutes > self.max_bar_age_minutes:
            return self._unavailable(
                f"{session}; latest {self.timeframe} candle is stale "
                f"({age_minutes:.0f} min old)"
            )

        true_ranges = _true_ranges(candles)
        current_atr = fmean(true_ranges[-self.atr_period :])
        baseline_slice = true_ranges[
            -(self.baseline_bars + self.atr_period) : -self.atr_period
        ]
        baseline_atr = median(baseline_slice)
        if baseline_atr <= 0:
            return self._unavailable(f"{session}; MT5 ATR baseline is unavailable")

        ratio = current_atr / baseline_atr
        abnormal = ratio >= self.abnormal_ratio
        state = "abnormal" if abnormal else "normal"
        return VolatilityRisk(
            abnormal=abnormal,
            score=round(ratio, 4),
            summary=(
                f"{session}; {self.timeframe} ATR {current_atr:.5g}, "
                f"{ratio:.2f}x baseline ({state})"
            ),
            provider=self.name,
            is_live=True,
        )

    def _unavailable(self, summary: str) -> VolatilityRisk:
        return VolatilityRisk(
            abnormal=False,
            score=0.0,
            summary=summary,
            provider=self.name,
            is_live=False,
        )


def _true_ranges(candles: list[Candle]) -> list[float]:
    ranges: list[float] = []
    for previous, current in zip(candles, candles[1:], strict=False):
        ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return ranges


def _utc_session(at: datetime) -> str:
    hour = at.astimezone(timezone.utc).hour
    if 0 <= hour < 7:
        return "Asia session"
    if 7 <= hour < 12:
        return "London session"
    if 12 <= hour < 16:
        return "London/New York overlap"
    if 16 <= hour < 21:
        return "New York session"
    return "Rollover/off-hours"


def create_volatility_provider(
    settings: Settings | None = None,
    bridge: MT5BridgePort | None = None,
):
    configured = settings or Settings()
    if configured.volatility_provider == "mock":
        return MockVolatilityProvider()
    if configured.volatility_provider == "mt5":
        if bridge is None:
            raise ValueError("MT5 bridge is required for VOLATILITY_PROVIDER=mt5")
        return Mt5VolatilityProvider(bridge, configured)
    raise ValueError(
        f"Unsupported volatility provider: {configured.volatility_provider}"
    )
