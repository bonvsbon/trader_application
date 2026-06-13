"""MT5 account status and editable runtime bridge configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_auth_context, get_operator
from app.api.deps import get_bridge
from app.auth.service import AuthContext
from app.bridge.base import (
    get_effective_mt5_config,
    replace_configured_bridge,
)
from app.core.config import get_settings
from app.core.enums import AccountType, BridgeHealth
from app.domain.models import AccountInfo, Mt5RuntimeConfig
from app.domain.ports import MT5BridgePort
from app.persistence.db import get_db
from app.persistence.repositories import (
    AuditRepository,
    LogRepository,
    Mt5ConfigRepository,
)
from app.workflow.scheduler import reset_scheduler

router = APIRouter(prefix="/api/account", tags=["account"])


def _account_dict(account: AccountInfo) -> dict:
    return {
        "account_type": account.account_type.value,
        "login": account.login,
        "server": account.server,
        "currency": account.currency,
        "balance": account.balance,
        "equity": account.equity,
        "margin": account.margin,
        "free_margin": account.free_margin,
        "free_margin_pct": round(account.free_margin_pct, 1),
        "leverage": account.leverage,
    }


def _bridge_status(bridge: MT5BridgePort) -> dict:
    try:
        health = bridge.health()
        health_value = health.health.value
        heartbeat = health.last_heartbeat
        detail = health.detail
    except Exception as exc:
        health_value, heartbeat, detail = BridgeHealth.UNKNOWN.value, None, str(exc)

    validation_problems: list[str] = []
    try:
        snapshot = getattr(bridge, "account_snapshot", None)
        if callable(snapshot):
            account, validation_problems = snapshot()
        else:
            account = bridge.account_info()
        account_data = _account_dict(account)
    except Exception:
        account_data = {"account_type": AccountType.UNKNOWN.value}

    return {
        "bridge_health": health_value,
        "last_heartbeat": heartbeat.isoformat() if heartbeat else None,
        "detail": detail,
        "account": account_data,
        "configuration_match": not validation_problems,
        "configuration_problems": validation_problems,
    }


def _config_dict(config: Mt5RuntimeConfig, *, source: str, metadata=None) -> dict:
    data = config.model_dump(mode="json")
    data.update(
        source=source,
        stores_password=False,
        ea_shared_secret_configured=bool(get_settings().mt5_ea_shared_secret),
        updated_by=metadata.updated_by if metadata else None,
        updated_at=metadata.updated_at.isoformat() if metadata else None,
        mt5_account_id=metadata.mt5_account_id if metadata else None,
    )
    return data


@router.get("")
def account_status(
    bridge: MT5BridgePort = Depends(get_bridge),
    context: AuthContext = Depends(get_auth_context),
) -> dict:
    return _bridge_status(bridge)


def _ensure_config_owner(metadata, context: AuthContext) -> None:
    if context.user_id is None:
        return
    if metadata is None or metadata.mt5_account_id != context.mt5_account_id:
        raise HTTPException(
            status_code=403,
            detail="MT5 configuration is not owned by the current user",
        )


def _ensure_config_matches_login(
    config: Mt5RuntimeConfig,
    context: AuthContext,
) -> None:
    if context.user_id is None or config.bridge_type != "ea_socket":
        return
    if (
        config.expected_login != context.mt5_login
        or (config.expected_server or "").casefold()
        != (context.mt5_server or "").casefold()
        or config.expected_account_type.value != context.account_type
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "EA socket configuration must match the current user's "
                "registered MT5 login, server, and account type"
            ),
        )


@router.get("/configuration")
def account_configuration(
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
    context: AuthContext = Depends(get_auth_context),
) -> dict:
    repository = Mt5ConfigRepository(session, context.mt5_account_id or 1)
    row = repository.get()
    _ensure_config_owner(row, context)
    config = repository.get_config() or get_effective_mt5_config()
    return _config_dict(config, source="database" if row else "environment", metadata=row)


@router.put("/configuration")
def update_account_configuration(
    config: Mt5RuntimeConfig,
    session: Session = Depends(get_db),
    operator: str = Depends(get_operator),
    context: AuthContext = Depends(get_auth_context),
) -> dict:
    repository = Mt5ConfigRepository(session, context.mt5_account_id or 1)
    _ensure_config_owner(repository.get(), context)
    _ensure_config_matches_login(config, context)
    row = repository.save(config, updated_by=operator)
    AuditRepository(session, context.mt5_account_id or 1).write(
        event="mt5.configuration_updated",
        payload={
            **config.model_dump(mode="json"),
            "updated_by": operator,
            "password_stored": False,
        },
    )
    LogRepository(session).add(
        "WARNING",
        "mt5-config",
        "MT5 runtime configuration changed; workflow stopped and bridge restarted",
        {
            "updated_by": operator,
            "bridge_type": config.bridge_type,
            "expected_login": config.expected_login,
            "expected_server": config.expected_server,
            "expected_account_type": config.expected_account_type.value,
        },
    )
    # The bridge replacement is a process-wide side effect, so make the config
    # durable before activating it.
    session.commit()
    reset_scheduler()
    bridge = replace_configured_bridge(config)
    return {
        "configuration": _config_dict(config, source="database", metadata=row),
        "connection": _bridge_status(bridge),
    }


@router.post("/configuration/test")
def test_account_configuration(
    bridge: MT5BridgePort = Depends(get_bridge),
    operator: str = Depends(get_operator),
    context: AuthContext = Depends(get_auth_context),
) -> dict:
    return _bridge_status(bridge)
