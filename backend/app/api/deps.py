"""FastAPI dependencies — wire the request-scoped session, bridge, and services."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.bridge.base import get_configured_bridge
from app.core.config import Settings, get_settings
from app.domain.ports import MT5BridgePort
from app.execution.order_service import OrderService
from app.news.base import create_news_provider
from app.persistence.db import get_db
from app.volatility.base import create_volatility_provider


def get_bridge(settings: Settings = Depends(get_settings)) -> MT5BridgePort:
    return get_configured_bridge()


def get_order_service(
    session: Session = Depends(get_db),
    bridge: MT5BridgePort = Depends(get_bridge),
    settings: Settings = Depends(get_settings),
) -> OrderService:
    return OrderService(
        session,
        bridge,
        settings=settings,
        news_provider=create_news_provider(settings),
        volatility_provider=create_volatility_provider(settings),
    )
