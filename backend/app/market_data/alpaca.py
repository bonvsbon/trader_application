"""Alpaca stock quote WebSocket adapter."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import websockets

from app.core.config import Settings
from app.market_data.models import MarketDataConfig


class MarketDataConnectionError(RuntimeError):
    pass


def validate_alpaca_endpoint(endpoint: str, settings: Settings) -> None:
    parsed = urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    if host not in set(settings.market_data_allowed_host_list):
        raise MarketDataConnectionError(
            f"Market-data host {host!r} is not in MARKET_DATA_ALLOWED_HOSTS"
        )
    if parsed.scheme != "wss":
        raise MarketDataConnectionError("Remote market-data endpoints must use WSS")


def _credentials(config: MarketDataConfig) -> tuple[str, str]:
    if not config.api_key_ref or not config.api_secret_ref:
        raise MarketDataConnectionError("Alpaca credential references are missing")
    key = os.getenv(config.api_key_ref, "")
    secret = os.getenv(config.api_secret_ref, "")
    if not key or not secret:
        raise MarketDataConnectionError(
            "Alpaca credentials are not configured in the referenced environment variables"
        )
    return key, secret


def _messages(raw: str | bytes) -> list[dict]:
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MarketDataConnectionError("Alpaca returned invalid JSON") from exc
    if isinstance(payload, dict):
        return [payload]
    if not isinstance(payload, list):
        raise MarketDataConnectionError("Alpaca returned an invalid message envelope")
    return [item for item in payload if isinstance(item, dict)]


async def _authenticate(connection, config: MarketDataConfig) -> None:
    key, secret = _credentials(config)
    connected = _messages(await connection.recv())
    if not any(
        item.get("T") == "success" and item.get("msg") == "connected"
        for item in connected
    ):
        raise MarketDataConnectionError("Alpaca did not confirm the connection")
    await connection.send(
        json.dumps({"action": "auth", "key": key, "secret": secret})
    )
    authenticated = _messages(await connection.recv())
    if not any(
        item.get("T") == "success" and item.get("msg") == "authenticated"
        for item in authenticated
    ):
        message = next(
            (str(item.get("msg")) for item in authenticated if item.get("msg")),
            "authentication failed",
        )
        raise MarketDataConnectionError(f"Alpaca {message}")


def _stream_url(config: MarketDataConfig) -> str:
    return f"{config.endpoint.rstrip('/')}/{config.feed}"


async def inspect_alpaca_provider(
    config: MarketDataConfig,
    settings: Settings,
) -> dict:
    validate_alpaca_endpoint(config.endpoint, settings)
    try:
        async with websockets.connect(
            _stream_url(config),
            open_timeout=config.timeout_sec,
            close_timeout=3,
            ping_interval=20,
            max_size=1_000_000,
        ) as connection:
            await _authenticate(connection, config)
    except MarketDataConnectionError:
        raise
    except Exception as exc:
        raise MarketDataConnectionError(str(exc) or type(exc).__name__) from exc
    return {
        "provider": "alpaca",
        "feed": config.feed,
        "feed_status": config.feed_status,
    }


async def alpaca_quote_stream(
    config: MarketDataConfig,
    symbols: list[str],
    settings: Settings,
) -> AsyncIterator[dict]:
    validate_alpaca_endpoint(config.endpoint, settings)
    try:
        async with websockets.connect(
            _stream_url(config),
            open_timeout=config.timeout_sec,
            close_timeout=3,
            ping_interval=20,
            max_size=1_000_000,
        ) as connection:
            await _authenticate(connection, config)
            await connection.send(
                json.dumps({"action": "subscribe", "quotes": symbols})
            )
            while True:
                for item in _messages(await connection.recv()):
                    if item.get("T") == "error":
                        raise MarketDataConnectionError(
                            f"Alpaca {item.get('msg', 'stream error')}"
                        )
                    if item.get("T") != "q":
                        continue
                    yield {
                        "symbol": item.get("S"),
                        "bid": item.get("bp"),
                        "ask": item.get("ap"),
                        "bid_size": item.get("bs"),
                        "ask_size": item.get("as"),
                        "spread_points": (
                            round(float(item["ap"]) - float(item["bp"]), 8)
                            if item.get("ap") is not None
                            and item.get("bp") is not None
                            else None
                        ),
                        "time": item.get("t"),
                        "exchange": item.get("z"),
                    }
    except MarketDataConnectionError:
        raise
    except Exception as exc:
        raise MarketDataConnectionError(str(exc) or type(exc).__name__) from exc
