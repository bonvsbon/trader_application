from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import ws
from app.domain.models import SymbolQuote
from app.main import create_app


class QuoteBridge:
    def quote(self, symbol: str) -> SymbolQuote:
        return SymbolQuote(
            symbol=symbol,
            bid=100.0,
            ask=100.2,
            spread_points=20.0,
            time=datetime.now(timezone.utc),
        )


class PartialQuoteBridge(QuoteBridge):
    def quote(self, symbol: str) -> SymbolQuote:
        if symbol == "NVDA":
            raise RuntimeError("MQL5 EA error: quote unavailable")
        return super().quote(symbol)


def test_market_websocket_streams_requested_symbols(monkeypatch):
    monkeypatch.setattr(ws, "get_configured_bridge", lambda: QuoteBridge())
    monkeypatch.setattr(
        ws,
        "get_effective_mt5_config",
        lambda: SimpleNamespace(bridge_type="ea_socket"),
    )

    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws/market?symbols=XAUUSD,AAPL") as socket:
            payload = socket.receive_json()

    assert payload["source"] == "mt5:ea_socket"
    assert [quote["symbol"] for quote in payload["quotes"]] == ["XAUUSD", "AAPL"]
    assert payload["errors"] == []


def test_market_websocket_explains_unavailable_broker_symbol(monkeypatch):
    monkeypatch.setattr(ws, "get_configured_bridge", lambda: PartialQuoteBridge())
    monkeypatch.setattr(
        ws,
        "get_effective_mt5_config",
        lambda: SimpleNamespace(bridge_type="ea_socket"),
    )

    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws/market?symbols=XAUUSD,NVDA") as socket:
            payload = socket.receive_json()

    assert [quote["symbol"] for quote in payload["quotes"]] == ["XAUUSD"]
    assert payload["errors"][0]["symbol"] == "NVDA"
    assert payload["errors"][0]["code"] == "broker_symbol_unavailable"
    assert "Alpaca IEX" in payload["errors"][0]["hint"]
