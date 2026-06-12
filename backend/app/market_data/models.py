"""Validated runtime configuration for read-only market data."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MarketDataProvider = Literal["mt5", "alpaca", "disabled"]
AlpacaFeed = Literal["iex", "sip", "delayed_sip"]


class MarketDataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    provider: MarketDataProvider = "mt5"
    endpoint: str = Field(
        default="wss://stream.data.alpaca.markets/v2",
        max_length=2048,
    )
    feed: AlpacaFeed = "iex"
    api_key_ref: str | None = Field(
        default=None,
        pattern=r"^MARKET_DATA_[A-Z0-9_]+$",
        max_length=128,
    )
    api_secret_ref: str | None = Field(
        default=None,
        pattern=r"^MARKET_DATA_[A-Z0-9_]+$",
        max_length=128,
    )
    default_symbols: list[str] = Field(default_factory=lambda: ["XAUUSD"], max_length=25)
    max_symbols: int = Field(default=25, ge=1, le=100)
    timeout_sec: float = Field(default=10.0, ge=1.0, le=60.0)

    @field_validator("default_symbols")
    @classmethod
    def _clean_symbols(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip().upper() for value in values if value.strip()]
        return list(dict.fromkeys(cleaned))

    @model_validator(mode="after")
    def _validate_provider(self) -> MarketDataConfig:
        if self.provider == "disabled":
            self.enabled = False
        if self.enabled and self.provider == "alpaca":
            if not self.api_key_ref or not self.api_secret_ref:
                raise ValueError(
                    "Enabled Alpaca provider requires API key and secret references"
                )
            parsed = urlparse(self.endpoint)
            if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
                raise ValueError("Alpaca endpoint must be a ws(s) URL")
            self.endpoint = self.endpoint.rstrip("/")
        if self.enabled and not self.default_symbols:
            raise ValueError("Enabled market data requires at least one default symbol")
        return self

    @property
    def feed_status(self) -> str:
        if self.provider == "mt5":
            return "broker-realtime"
        if self.provider != "alpaca":
            return "disabled"
        return {
            "iex": "realtime-single-exchange",
            "sip": "realtime-consolidated",
            "delayed_sip": "delayed-consolidated",
        }[self.feed]
