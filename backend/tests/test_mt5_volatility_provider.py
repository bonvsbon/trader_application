from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import Settings
from app.domain.models import Candle
from app.volatility.base import Mt5VolatilityProvider, create_volatility_provider


class CandleBridge:
    def __init__(self, candles: list[Candle]) -> None:
        self._candles = candles
        self.calls: list[tuple[str, str, int]] = []

    def candles(self, symbol: str, timeframe: str, count: int) -> list[Candle]:
        self.calls.append((symbol, timeframe, count))
        return self._candles[-count:]


def _candles(
    *,
    baseline_range: float = 2.0,
    recent_range: float = 2.0,
    stale: bool = False,
) -> list[Candle]:
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    if stale:
        end -= timedelta(hours=3)
    rows: list[Candle] = []
    price = 2400.0
    for index in range(20):
        candle_range = recent_range if index >= 16 else baseline_range
        rows.append(
            Candle(
                time=end - timedelta(minutes=15 * (19 - index)),
                open=price,
                high=price + candle_range / 2,
                low=price - candle_range / 2,
                close=price,
                volume=100,
            )
        )
    return rows


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "volatility_provider": "mt5",
        "volatility_timeframe": "M15",
        "volatility_atr_period": 4,
        "volatility_baseline_bars": 12,
        "volatility_abnormal_ratio": 2.0,
        "volatility_max_bar_age_minutes": 45,
    }
    values.update(overrides)
    return Settings(**values)


def test_mt5_volatility_reports_fresh_normal_market():
    bridge = CandleBridge(_candles())
    provider = Mt5VolatilityProvider(bridge, _settings())

    result = provider.volatility_risk("xauusd")

    assert result.provider == "mt5"
    assert result.is_live is True
    assert result.abnormal is False
    assert result.score == pytest.approx(1.0)
    assert bridge.calls == [("XAUUSD", "M15", 17)]


def test_mt5_volatility_blocks_abnormal_recent_atr():
    provider = Mt5VolatilityProvider(
        CandleBridge(_candles(recent_range=6.0)),
        _settings(),
    )

    result = provider.volatility_risk("XAUUSD")

    assert result.is_live is True
    assert result.abnormal is True
    assert result.score == pytest.approx(3.0)
    assert "abnormal" in result.summary


def test_mt5_volatility_marks_stale_market_data_unavailable():
    provider = Mt5VolatilityProvider(
        CandleBridge(_candles(stale=True)),
        _settings(),
    )

    result = provider.volatility_risk("XAUUSD")

    assert result.provider == "mt5"
    assert result.is_live is False
    assert result.abnormal is False
    assert "stale" in result.summary


def test_mt5_volatility_marks_insufficient_history_unavailable():
    provider = Mt5VolatilityProvider(
        CandleBridge(_candles()[:10]),
        _settings(),
    )

    result = provider.volatility_risk("XAUUSD")

    assert result.is_live is False
    assert "Insufficient" in result.summary


def test_factory_requires_bridge_for_mt5_provider():
    with pytest.raises(ValueError, match="bridge is required"):
        create_volatility_provider(_settings())
