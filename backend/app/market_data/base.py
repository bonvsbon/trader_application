"""Effective read-only market-data configuration."""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, get_settings
from app.market_data.models import MarketDataConfig


def default_market_data_config(settings: Settings | None = None) -> MarketDataConfig:
    settings = settings or get_settings()
    return MarketDataConfig(
        enabled=settings.market_data_enabled,
        provider=settings.market_data_provider,
        endpoint=settings.market_data_endpoint,
        feed=settings.market_data_feed,
        api_key_ref=(
            settings.market_data_api_key_ref
            if settings.market_data_provider == "alpaca"
            else None
        ),
        api_secret_ref=(
            settings.market_data_api_secret_ref
            if settings.market_data_provider == "alpaca"
            else None
        ),
        default_symbols=settings.market_data_default_symbol_list,
        max_symbols=settings.market_data_max_symbols,
        timeout_sec=settings.market_data_timeout_sec,
    )


def load_market_data_config(settings: Settings | None = None) -> MarketDataConfig:
    settings = settings or get_settings()
    try:
        from app.persistence.db import SessionLocal
        from app.persistence.repositories import MarketDataConfigRepository

        with SessionLocal() as session:
            return (
                MarketDataConfigRepository(session).get_config()
                or default_market_data_config(settings)
            )
    except SQLAlchemyError:
        return default_market_data_config(settings)
