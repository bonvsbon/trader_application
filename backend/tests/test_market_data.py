from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import settings as settings_routes
from app.core.config import get_settings
from app.main import create_app
from app.market_data.alpaca import MarketDataConnectionError, validate_alpaca_endpoint
from app.market_data.models import MarketDataConfig
from app.persistence.db import get_db


def _config(**overrides) -> dict:
    payload = {
        "enabled": True,
        "provider": "alpaca",
        "endpoint": "wss://stream.data.alpaca.markets/v2",
        "feed": "iex",
        "api_key_ref": "MARKET_DATA_ALPACA_KEY",
        "api_secret_ref": "MARKET_DATA_ALPACA_SECRET",
        "default_symbols": ["AAPL", "MSFT"],
        "max_symbols": 25,
        "timeout_sec": 10,
    }
    payload.update(overrides)
    return payload


def test_market_data_config_requires_secret_references():
    config = MarketDataConfig.model_validate(_config())
    assert config.feed_status == "realtime-single-exchange"


def test_alpaca_endpoint_requires_allowlist_and_wss(make_settings):
    settings = make_settings(market_data_allowed_hosts="stream.data.alpaca.markets")
    with pytest.raises(MarketDataConnectionError, match="WSS"):
        validate_alpaca_endpoint(
            "ws://stream.data.alpaca.markets/v2",
            settings,
        )
    with pytest.raises(MarketDataConnectionError, match="ALLOWED_HOSTS"):
        validate_alpaca_endpoint("wss://other.example.com/v2", settings)


def test_market_data_api_persists_config_and_tests_connection(
    session,
    make_settings,
    monkeypatch,
):
    app = create_app()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: make_settings()

    async def fake_inspect(config, settings):
        return {
            "provider": "alpaca",
            "feed": config.feed,
            "feed_status": config.feed_status,
        }

    monkeypatch.setattr(settings_routes, "inspect_alpaca_provider", fake_inspect)
    with TestClient(app) as client:
        saved = client.put("/api/settings/market-data", json=_config())
        tested = client.post("/api/settings/market-data/test")

    assert saved.status_code == 200
    assert saved.json()["stores_plaintext_secret"] is False
    assert tested.status_code == 200
    assert tested.json()["healthy"] is True
    assert tested.json()["feed_status"] == "realtime-single-exchange"
