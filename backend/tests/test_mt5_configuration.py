from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.bridge.base import AccountGuardBridge, create_bridge
from app.bridge.mock_bridge import MockBridge
from app.core.enums import AccountType
from app.domain.models import Mt5RuntimeConfig
from app.persistence.repositories import Mt5ConfigRepository


def test_mt5_configuration_round_trips_without_password(session):
    config = Mt5RuntimeConfig(
        bridge_type="ea_socket",
        host="127.0.0.1",
        port=5555,
        expected_login=123456,
        expected_server="Broker-Demo",
        expected_account_type=AccountType.DEMO,
    )

    row = Mt5ConfigRepository(session).save(config, updated_by="owner")
    loaded = Mt5ConfigRepository(session).get_config()

    assert loaded == config
    assert row.updated_by == "owner"
    assert "password" not in loaded.model_dump()


def test_account_guard_blocks_mismatched_login(make_settings):
    config = Mt5RuntimeConfig(
        bridge_type="mock",
        expected_login=999999,
        expected_account_type=AccountType.DEMO,
    )
    bridge = AccountGuardBridge(
        MockBridge(settings=make_settings(), account_type=AccountType.DEMO),
        config,
    )

    raw_account, problems = bridge.account_snapshot()
    guarded_account = bridge.account_info()

    assert raw_account.account_type is AccountType.DEMO
    assert any("login" in problem.lower() for problem in problems)
    assert guarded_account.account_type is AccountType.UNKNOWN


def test_live_bridge_requires_complete_expected_account():
    config = Mt5RuntimeConfig(bridge_type="ea_socket")
    problems = config.account_problems(
        MockBridge().account_info()
    )

    assert any("login" in problem.lower() for problem in problems)
    assert any("server" in problem.lower() for problem in problems)
    assert any("account type" in problem.lower() for problem in problems)


def test_mt5_configuration_rejects_password_fields():
    with pytest.raises(ValidationError):
        Mt5RuntimeConfig.model_validate(
            {
                "bridge_type": "ea_socket",
                "password": "must-not-be-stored",
            }
        )


def test_ea_socket_requires_environment_managed_shared_secret(make_settings):
    settings = make_settings(mt5_bridge_type="ea_socket", mt5_ea_shared_secret="")
    config = Mt5RuntimeConfig(
        bridge_type="ea_socket",
        expected_login=123,
        expected_server="Broker-Demo",
        expected_account_type=AccountType.DEMO,
    )

    with pytest.raises(ValueError, match="MT5_EA_SHARED_SECRET"):
        create_bridge(settings, config)


def test_remote_ea_socket_bind_requires_explicit_opt_in(make_settings):
    settings = make_settings(
        mt5_bridge_type="ea_socket",
        mt5_ea_shared_secret="test-secret",
        mt5_ea_allow_remote_bind=False,
    )
    config = Mt5RuntimeConfig(
        bridge_type="ea_socket",
        host="0.0.0.0",
        expected_login=123,
        expected_server="Broker-Demo",
        expected_account_type=AccountType.DEMO,
    )

    with pytest.raises(ValueError, match="REMOTE_BIND"):
        create_bridge(settings, config)
