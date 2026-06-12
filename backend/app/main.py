"""FastAPI application factory.

Wires routers and the WebSocket. No business logic lives here — routes delegate
to services, which delegate to the order chokepoint and Risk Engine.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import ws
from app.api.auth import get_operator
from app.api.routes import (
    account,
    analysis,
    auth,
    dashboard,
    history,
    logs,
    orders,
    risk,
    settings as settings_routes,
    strategy,
    workflow,
)
from app.bridge.base import close_configured_bridge, get_effective_mt5_config
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        close_configured_bridge()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)

    app = FastAPI(title="ทางรอด API", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    for module in (
        dashboard,
        analysis,
        account,
        orders,
        risk,
        strategy,
        settings_routes,
        workflow,
        logs,
        history,
    ):
        app.include_router(module.router, dependencies=[Depends(get_operator)])
    app.include_router(ws.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        mt5_config = get_effective_mt5_config()
        return {
            "status": "ok",
            "version": __version__,
            "trading_mode": settings.trading_mode.value,
            "bridge_type": mt5_config.bridge_type,
            "mt5_configuration_enabled": mt5_config.enabled,
            "auto_real_full_enabled": settings.auto_real_full_enabled(),
        }

    logger.info(
        "ทางรอด API ready (mode=%s, bridge=%s, auto_real_full=%s)",
        settings.trading_mode.value,
        settings.mt5_bridge_type,
        settings.auto_real_full_enabled(),
    )
    return app


app = create_app()
