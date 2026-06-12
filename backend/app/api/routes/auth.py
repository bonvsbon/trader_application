"""Login and first-user bootstrap using MT5 login as the username."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.api.auth import get_auth_context
from app.auth.service import AuthContext, AuthError, AuthService, SessionCredentials
from app.core.config import Settings, get_settings
from app.persistence.db import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mt5_login: int = Field(gt=0)
    app_password: str = Field(min_length=10, max_length=128)


class BootstrapBody(LoginBody):
    display_name: str = Field(min_length=2, max_length=100)
    mt5_server: str = Field(min_length=2, max_length=128)
    account_type: Literal["DEMO", "REAL"]

    @field_validator("display_name", "mt5_server")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("must contain at least 2 non-whitespace characters")
        return value


def _user_dict(context: AuthContext) -> dict:
    return {
        "id": context.user_id,
        "mt5_login": context.mt5_login,
        "display_name": context.display_name,
        "role": context.role,
        "mt5_account": {
            "id": context.mt5_account_id,
            "login": context.mt5_login,
            "server": context.mt5_server,
            "account_type": context.account_type,
        }
        if context.mt5_account_id is not None
        else None,
    }


def _set_session_cookie(
    response: Response,
    credentials: SessionCredentials,
    settings: Settings,
) -> None:
    response.set_cookie(
        settings.auth_cookie_name,
        credentials.token,
        max_age=settings.auth_session_hours * 3600,
        httponly=True,
        secure=settings.app_env.lower() == "prod",
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        settings.auth_csrf_cookie_name,
        credentials.csrf_token,
        max_age=settings.auth_session_hours * 3600,
        httponly=False,
        secure=settings.app_env.lower() == "prod",
        samesite="strict",
        path="/",
    )


def _session_response(credentials: SessionCredentials) -> dict:
    return {
        "authenticated": True,
        "csrf_token": credentials.csrf_token,
        "expires_at": credentials.expires_at.isoformat(),
        "user": _user_dict(credentials.context),
    }


@router.get("/status")
def auth_status(
    request: Request,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    service = AuthService(session, settings)
    context = service.context_for_token(
        request.cookies.get(settings.auth_cookie_name, "")
    )
    csrf_token = request.cookies.get(settings.auth_csrf_cookie_name, "")
    return {
        "enabled": settings.user_auth_enabled,
        "bootstrap_required": service.bootstrap_required(),
        "authenticated": context is not None or not settings.user_auth_enabled,
        "user": _user_dict(context) if context else None,
        "csrf_token": (
            csrf_token
            if context
            and service.validate_csrf(
                request.cookies.get(settings.auth_cookie_name, ""),
                csrf_token,
            )
            else None
        ),
    }


@router.post("/bootstrap", status_code=status.HTTP_201_CREATED)
def bootstrap(
    body: BootstrapBody,
    response: Response,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        credentials = AuthService(session, settings).bootstrap(
            mt5_login=body.mt5_login,
            app_password=body.app_password,
            display_name=body.display_name,
            mt5_server=body.mt5_server,
            account_type=body.account_type,
        )
    except AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _set_session_cookie(response, credentials, settings)
    return _session_response(credentials)


@router.post("/login")
def login(
    body: LoginBody,
    response: Response,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.user_auth_enabled:
        raise HTTPException(status_code=409, detail="User authentication is disabled")
    try:
        credentials = AuthService(session, settings).login(
            mt5_login=body.mt5_login,
            app_password=body.app_password,
        )
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    _set_session_cookie(response, credentials, settings)
    return _session_response(credentials)


@router.get("/me")
def me(context: AuthContext = Depends(get_auth_context)) -> dict:
    return {"authenticated": True, "user": _user_dict(context)}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    context: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    AuthService(session, settings).logout(
        request.cookies.get(settings.auth_cookie_name, "")
    )
    response.delete_cookie(settings.auth_cookie_name, path="/")
    response.delete_cookie(settings.auth_csrf_cookie_name, path="/")
    return {"authenticated": False}
