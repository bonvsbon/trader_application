from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.persistence.db import get_db
from app.persistence.repositories import Mt5ConfigRepository, UserRepository


def _client(session, settings):
    app = create_app()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def _bootstrap(client: TestClient):
    return client.post(
        "/api/auth/bootstrap",
        json={
            "mt5_login": 7654321,
            "app_password": "separate-app-password",
            "display_name": "Gold Owner",
            "mt5_server": "Broker-Demo",
            "account_type": "DEMO",
        },
    )


def test_first_user_bootstrap_login_and_csrf(session, make_settings):
    settings = make_settings(user_auth_enabled=True)
    with _client(session, settings) as client:
        initial = client.get("/api/auth/status")
        created = _bootstrap(client)
        status = client.get("/api/auth/status")
        dashboard = client.get("/api/dashboard")
        blocked_logout = client.post("/api/auth/logout")
        logout = client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": created.json()["csrf_token"]},
        )
        protected = client.get("/api/dashboard")

    assert initial.json()["bootstrap_required"] is True
    assert created.status_code == 201
    assert created.json()["user"]["mt5_login"] == 7654321
    assert status.json()["authenticated"] is True
    assert dashboard.status_code == 200
    assert blocked_logout.status_code == 403
    assert logout.status_code == 200
    assert protected.status_code == 401


def test_login_uses_mt5_login_and_separate_app_password(session, make_settings):
    settings = make_settings(user_auth_enabled=True)
    with _client(session, settings) as client:
        created = _bootstrap(client)
        client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": created.json()["csrf_token"]},
        )
        wrong = client.post(
            "/api/auth/login",
            json={"mt5_login": 7654321, "app_password": "wrong-password"},
        )
        logged_in = client.post(
            "/api/auth/login",
            json={
                "mt5_login": 7654321,
                "app_password": "separate-app-password",
            },
        )

    assert wrong.status_code == 401
    assert logged_in.status_code == 200
    assert logged_in.json()["user"]["mt5_account"]["server"] == "Broker-Demo"
    assert "password" not in logged_in.json()["user"]["mt5_account"]


def test_bootstrap_binds_legacy_mt5_configuration_to_owner(session, make_settings):
    settings = make_settings(user_auth_enabled=True)
    with _client(session, settings) as client:
        created = _bootstrap(client)

    user = UserRepository(session).get_by_mt5_login(7654321)
    config = Mt5ConfigRepository(session).get()
    assert created.status_code == 201
    assert user is not None
    assert config is not None
    assert config.mt5_account_id == created.json()["user"]["mt5_account"]["id"]


def test_ea_socket_config_must_match_logged_in_mt5_identity(session, make_settings):
    settings = make_settings(user_auth_enabled=True)
    with _client(session, settings) as client:
        created = _bootstrap(client)
        csrf = created.json()["csrf_token"]
        mismatch = client.put(
            "/api/account/configuration",
            headers={"X-CSRF-Token": csrf},
            json={
                "enabled": True,
                "bridge_type": "ea_socket",
                "host": "127.0.0.1",
                "port": 5555,
                "timeout_sec": 5,
                "heartbeat_max_age_sec": 15,
                "expected_login": 111111,
                "expected_server": "Other-Server",
                "expected_account_type": "DEMO",
            },
        )

    assert mismatch.status_code == 422
    assert "current user's registered MT5" in mismatch.json()["detail"]
