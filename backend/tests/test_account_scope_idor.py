"""Account-scope and IDOR regression tests for trading persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.auth.service import hash_password
from app.core.enums import OrderSide, OrderState
from app.core.config import get_settings
from app.domain.models import ClosedTrade, Mt5RuntimeConfig, OrderRequest
from app.main import create_app
from app.persistence.db import get_db
from app.persistence.repositories import (
    ClosedTradeRepository,
    Mt5ConfigRepository,
    Mt5AccountRepository,
    OrderRepository,
    TradeProposalRepository,
    UserRepository,
)


def _client(session, settings) -> TestClient:
    app = create_app()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def _create_identity(session, *, login: int, server: str):
    user = UserRepository(session).create(
        mt5_login=login,
        display_name=f"Owner {login}",
        password_hash=hash_password("account-password"),
        is_admin=True,
    )
    return Mt5AccountRepository(session).create(
        owner_user_id=user.id,
        login=login,
        server=server,
        account_type="DEMO",
        display_name=f"{server} / {login}",
    )


def test_repositories_scope_keys_tickets_and_ids_per_account(session):
    account_a = _create_identity(session, login=10001, server="Broker-A")
    account_b = _create_identity(session, login=10002, server="Broker-B")
    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.1,
        idempotency_key="same-key-on-two-accounts",
    )
    order_a = OrderRepository(session, account_a.id).create(
        request,
        state=OrderState.FILLED.value,
        decision="ALLOW",
        account_type="DEMO",
        trading_mode="MANUAL_ONLY",
    )
    order_b = OrderRepository(session, account_b.id).create(
        request,
        state=OrderState.FILLED.value,
        decision="ALLOW",
        account_type="DEMO",
        trading_mode="MANUAL_ONLY",
    )
    trade = ClosedTrade(
        ticket=7001,
        symbol="XAUUSD",
        profit=10,
        close_time=datetime.now(timezone.utc),
    )
    ClosedTradeRepository(session, account_a.id).upsert_from_bridge([trade])
    ClosedTradeRepository(session, account_b.id).upsert_from_bridge([trade])
    config_a = Mt5ConfigRepository(session, account_a.id).save(
        Mt5RuntimeConfig(expected_login=account_a.login),
        updated_by="owner-a",
    )
    config_b = Mt5ConfigRepository(session, account_b.id).save(
        Mt5RuntimeConfig(expected_login=account_b.login),
        updated_by="owner-b",
    )

    assert order_a.id != order_b.id
    assert config_a.id != config_b.id
    assert OrderRepository(session, account_a.id).list_recent() == [order_a]
    assert OrderRepository(session, account_b.id).list_recent() == [order_b]
    assert Mt5ConfigRepository(session, account_a.id).get() == config_a
    assert Mt5ConfigRepository(session, account_b.id).get() == config_b
    assert ClosedTradeRepository(session, account_a.id).get_by_ticket(7001).mt5_account_id == account_a.id
    assert ClosedTradeRepository(session, account_b.id).get_by_ticket(7001).mt5_account_id == account_b.id


def test_user_a_cannot_read_or_mutate_user_b_trading_rows(
    session,
    make_settings,
):
    account_a = _create_identity(session, login=20001, server="Broker-A")
    account_b = _create_identity(session, login=20002, server="Broker-B")
    order_b = OrderRepository(session, account_b.id).create(
        OrderRequest(
            symbol="XAUUSD",
            side=OrderSide.BUY,
            volume=0.1,
            idempotency_key="private-order-b",
        ),
        state=OrderState.PENDING_APPROVAL.value,
        decision="ALLOW",
        account_type="DEMO",
        trading_mode="MANUAL_ONLY",
    )
    ClosedTradeRepository(session, account_b.id).upsert_from_bridge(
        [
            ClosedTrade(
                ticket=88002,
                symbol="XAUUSD",
                profit=-10,
                close_time=datetime.now(timezone.utc),
            )
        ]
    )
    proposal_b = TradeProposalRepository(session, account_b.id).create(
        status="DRAFT",
        symbol="XAUUSD",
        side="BUY",
        entry_price=2350,
        sl=2349,
        tp=2352,
        volume=0.1,
        risk_pct=1,
        strategy_name="IDOR_TEST",
        strategy_reason="Private proposal owned by account B",
        ai_summary=None,
        ai_confidence=None,
        risk_decision="ALLOW",
        risk_reasons=[],
        risk_warnings=[],
        created_by="test",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    session.commit()

    settings = make_settings(user_auth_enabled=True, auth_bootstrap_enabled=False)
    with _client(session, settings) as client:
        login = client.post(
            "/api/auth/login",
            json={"mt5_login": 20001, "app_password": "account-password"},
        )
        csrf = login.json()["csrf_token"]
        recent = client.get("/api/orders/recent")
        history = client.get("/api/history/trades")
        proposals = client.get("/api/proposals")
        approve_b = client.post(
            "/api/orders/approve",
            headers={"X-CSRF-Token": csrf},
            json={"idempotency_key": order_b.idempotency_key},
        )
        review_b = client.post(
            "/api/history/review/88002",
            headers={"X-CSRF-Token": csrf},
            json={"note": "Unauthorized edit"},
        )
        submit_b = client.post(
            f"/api/proposals/{proposal_b.id}/submit",
            headers={"X-CSRF-Token": csrf},
        )

    assert login.status_code == 200
    assert login.json()["user"]["mt5_account"]["id"] == account_a.id
    assert recent.json() == []
    assert history.json() == []
    assert proposals.json() == []
    assert approve_b.status_code == 404
    assert review_b.status_code == 404
    assert submit_b.status_code == 409
