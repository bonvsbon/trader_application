"""Shared test fixtures.

Each test gets a fresh in-memory SQLite database (schema built from the ORM
metadata) and factories for settings and the order service, so the safety
chokepoint can be driven through every branch without a live bridge or DB.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.bridge.base import (
    close_configured_bridge,
    default_mt5_config,
    replace_configured_bridge,
)
from app.bridge.mock_bridge import MockBridge
from app.core.config import Settings, get_settings
from app.domain.models import NewsRisk, VolatilityRisk
from app.execution.order_service import OrderService
from app.persistence.entities import Base


class _LiveNewsProvider:
    name = "test-live"

    def news_risk(self, symbol: str) -> NewsRisk:
        return NewsRisk(
            summary="Test calendar clear",
            provider=self.name,
            is_live=True,
        )


class _LiveVolatilityProvider:
    name = "test-live"

    def volatility_risk(self, symbol: str) -> VolatilityRisk:
        return VolatilityRisk(
            summary="Test volatility normal",
            provider=self.name,
            is_live=True,
        )


_LIVE_NEWS = _LiveNewsProvider()
_LIVE_VOLATILITY = _LiveVolatilityProvider()


@pytest.fixture(autouse=True)
def isolate_runtime_auth_config(monkeypatch):
    """Tests opt into live integrations explicitly instead of inheriting local .env."""
    monkeypatch.setenv("USER_AUTH_ENABLED", "false")
    monkeypatch.setenv("MT5_BRIDGE_TYPE", "mock")
    monkeypatch.setenv("MT5_EXPECTED_LOGIN", "1000001")
    monkeypatch.setenv("MT5_EXPECTED_SERVER", "Mock-Server")
    monkeypatch.setenv("MT5_EXPECTED_ACCOUNT_TYPE", "DEMO")
    monkeypatch.setenv("NEWS_PROVIDER", "mock")
    monkeypatch.setenv("VOLATILITY_PROVIDER", "mock")
    get_settings.cache_clear()
    replace_configured_bridge(default_mt5_config(get_settings()))
    yield
    close_configured_bridge()
    get_settings.cache_clear()


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine) -> Session:
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    s = SessionLocal()
    try:
        yield s
        s.commit()
    finally:
        s.close()


@pytest.fixture
def make_settings():
    # _env_file=None keeps tests deterministic (ignores any local .env).
    def _make(**overrides) -> Settings:
        overrides.setdefault("mt5_bridge_type", "mock")
        return Settings(_env_file=None, **overrides)

    return _make


@pytest.fixture
def order_service(session, make_settings):
    def _make(
        settings: Settings | None = None,
        *,
        news_provider=_LIVE_NEWS,
        volatility_provider=_LIVE_VOLATILITY,
        **bridge_kwargs,
    ) -> OrderService:
        settings = settings or make_settings()
        bridge = MockBridge(settings=settings, **bridge_kwargs)
        return OrderService(
            session,
            bridge,
            settings=settings,
            news_provider=news_provider,
            volatility_provider=volatility_provider,
        )

    return _make
