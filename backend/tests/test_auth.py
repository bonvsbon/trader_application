"""Operator authentication policy."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.auth import authenticate_operator


def test_dev_auth_disabled_uses_trusted_local_actor(make_settings):
    assert authenticate_operator(make_settings(api_auth_required=False), None) == "local-dev"


def test_required_auth_accepts_matching_bearer_token(make_settings):
    settings = make_settings(
        api_auth_required=True,
        api_auth_token="secret-token",
        api_operator_name="owner",
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="secret-token")
    assert authenticate_operator(settings, credentials) == "owner"


def test_required_auth_rejects_missing_token(make_settings):
    settings = make_settings(api_auth_required=True, api_auth_token="secret-token")
    with pytest.raises(HTTPException) as exc:
        authenticate_operator(settings, None)
    assert exc.value.status_code == 401


def test_real_trading_requires_api_auth_in_safety_config(make_settings):
    problems = make_settings(
        allow_real_trading=True,
        api_auth_required=False,
    ).validate_safety()
    assert any("API_AUTH_REQUIRED" in problem for problem in problems)
