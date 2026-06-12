"""Application session and service-token authentication."""

from __future__ import annotations

import hmac

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.service import AuthContext, AuthService
from app.core.config import Settings, get_settings
from app.persistence.db import get_db

_bearer = HTTPBearer(auto_error=False)


def authenticate_operator(
    settings: Settings,
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    if not settings.api_auth_required:
        return "local-dev"
    if not settings.api_auth_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is required but no token is configured",
        )
    supplied = credentials.credentials if credentials else ""
    if not hmac.compare_digest(supplied, settings.api_auth_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing operator token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return settings.api_operator_name


def get_auth_context(
    request: Request,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthContext:
    if not settings.user_auth_enabled:
        actor = authenticate_operator(settings, credentials)
        return AuthContext(
            user_id=None,
            mt5_login=None,
            display_name=actor,
            role="service" if settings.api_auth_required else "local-dev",
            mt5_account_id=None,
            mt5_server=None,
            account_type=None,
            auth_source="bearer" if settings.api_auth_required else "local-dev",
        )

    if (
        credentials
        and settings.api_auth_token
        and hmac.compare_digest(credentials.credentials, settings.api_auth_token)
    ):
        return AuthContext(
            user_id=None,
            mt5_login=None,
            display_name=settings.api_operator_name,
            role="service",
            mt5_account_id=None,
            mt5_server=None,
            account_type=None,
            auth_source="bearer",
        )

    token = request.cookies.get(settings.auth_cookie_name, "")
    auth = AuthService(session, settings)
    context = auth.context_for_token(token)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required",
        )
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        csrf_token = request.headers.get("X-CSRF-Token", "")
        if not auth.validate_csrf(token, csrf_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing CSRF token",
            )
    return context


def get_operator(
    context: AuthContext = Depends(get_auth_context),
) -> str:
    return context.actor_name
