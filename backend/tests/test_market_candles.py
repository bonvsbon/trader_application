from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_order_service
from app.domain.models import Candle
from app.main import create_app


class CandleBridge:
    def candles(self, symbol: str, timeframe: str, count: int) -> list[Candle]:
        return [
            Candle(
                time=datetime(2026, 6, 13, tzinfo=timezone.utc),
                open=4200,
                high=4210,
                low=4195,
                close=4205,
                volume=100,
            )
        ]


def test_market_candles_are_read_only_bridge_data():
    app = create_app()
    app.dependency_overrides[get_order_service] = lambda: SimpleNamespace(
        bridge=CandleBridge()
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/market/candles",
            params={"symbol": "xauusd", "timeframe": "h1", "count": 42},
        )

    assert response.status_code == 200
    assert response.json() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "candles": [
            {
                "time": "2026-06-13T00:00:00+00:00",
                "open": 4200.0,
                "high": 4210.0,
                "low": 4195.0,
                "close": 4205.0,
                "volume": 100.0,
            }
        ],
    }
