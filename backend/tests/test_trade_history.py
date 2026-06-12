"""Trade history: closed-trade persistence, R-multiple, and summary.

R-multiple is realized profit ÷ planned risk at entry. Trades are deduped by
ticket so repeated workflow cycles never double-count, and unmatched trades are
still recorded (with no R).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.bridge.mock_bridge import MockBridge
from app.core.enums import OrderSide, OrderState
from app.domain.models import ClosedTrade, OrderRequest
from app.persistence.repositories import ClosedTradeRepository, OrderRepository
from app.workflow.runner import WorkflowRunner


def _make_order(session, *, key, ticket, planned_risk, side="BUY", volume=0.1):
    row = OrderRepository(session).create(
        OrderRequest(
            symbol="XAUUSD", side=OrderSide(side), volume=volume, sl=2349.0,
            risk_pct=1.0, idempotency_key=key,
        ),
        state=OrderState.FILLED.value, decision="ALLOW",
        account_type="DEMO", trading_mode="MANUAL_ONLY",
    )
    row.order_ticket = ticket
    row.planned_risk_amount = planned_risk
    session.flush()
    return row


def _trade(ticket, profit, symbol="XAUUSD"):
    return ClosedTrade(
        ticket=ticket, symbol=symbol, profit=profit,
        close_time=datetime.now(timezone.utc),
    )


def test_upsert_dedupes_by_ticket(session):
    repo = ClosedTradeRepository(session)
    trades = [_trade(111, 50.0)]
    assert repo.upsert_from_bridge(trades) == 1
    assert repo.upsert_from_bridge(trades) == 0  # same ticket -> no new row
    assert len(repo.list_recent()) == 1


def test_r_multiple_computed_from_matched_order(session):
    order = _make_order(session, key="match-001", ticket=111, planned_risk=25.0)
    repo = ClosedTradeRepository(session)
    repo.upsert_from_bridge([_trade(111, 50.0)], {111: order})
    row = repo.list_recent()[0]
    assert row.matched_order_id == order.id
    assert row.planned_risk_amount == 25.0
    assert row.r_multiple == 2.0
    assert row.side == "BUY"


def test_unmatched_trade_has_no_r(session):
    repo = ClosedTradeRepository(session)
    repo.upsert_from_bridge([_trade(999, -30.0)])
    row = repo.list_recent()[0]
    assert row.matched_order_id is None
    assert row.r_multiple is None
    assert row.planned_risk_amount is None


def test_summary_aggregates(session):
    o1 = _make_order(session, key="order-001", ticket=1, planned_risk=10.0)
    o2 = _make_order(session, key="order-002", ticket=2, planned_risk=10.0)
    repo = ClosedTradeRepository(session)
    repo.upsert_from_bridge(
        [_trade(1, 20.0), _trade(2, -10.0), _trade(3, 5.0)],
        {1: o1, 2: o2},
    )
    s = repo.summary()
    assert s["count"] == 3
    assert s["wins"] == 2
    assert s["losses"] == 1
    assert s["net_pnl"] == 15.0
    assert round(s["win_rate_pct"], 1) == round(2 / 3 * 100, 1)
    # ticket 1 -> R=+2.0, ticket 2 -> R=-1.0, ticket 3 unmatched -> no R
    assert s["rated_count"] == 2
    assert s["total_r"] == 1.0
    assert s["avg_r"] == 0.5


def test_place_order_persists_planned_risk(order_service, make_settings):
    svc = order_service(settings=make_settings())
    req = OrderRequest(
        symbol="XAUUSD", side=OrderSide.BUY, volume=0.1, sl=2349.0, tp=2352.0,
        risk_pct=1.0, idempotency_key="planrisk-0001",
    )
    result = svc.place_order(req)
    assert result.state is OrderState.FILLED
    row = svc.orders.get_by_key(req.idempotency_key)
    assert row.planned_risk_amount is not None
    assert row.planned_risk_amount > 0


def test_daily_breakdown_groups_by_close_day(session):
    from datetime import timedelta

    repo = ClosedTradeRepository(session)
    today = datetime.now(timezone.utc)
    yesterday = today - timedelta(days=1)
    repo.upsert_from_bridge([
        ClosedTrade(ticket=1, symbol="XAUUSD", profit=10.0, close_time=today),
        ClosedTrade(ticket=2, symbol="XAUUSD", profit=-4.0, close_time=today),
        ClosedTrade(ticket=3, symbol="XAUUSD", profit=6.0, close_time=yesterday),
    ])
    days = repo.daily_breakdown()
    assert len(days) == 2
    # Newest day first.
    assert days[0]["date"] == today.date().isoformat()
    assert days[0]["count"] == 2
    assert days[0]["net_pnl"] == 6.0
    assert days[1]["date"] == yesterday.date().isoformat()
    assert days[1]["count"] == 1


def test_list_losing_and_save_review(session):
    repo = ClosedTradeRepository(session)
    repo.upsert_from_bridge([
        _trade(1, 30.0),    # win — excluded
        _trade(2, -12.0),   # loss
        _trade(3, -5.0),    # loss
    ])
    losing = repo.list_losing()
    assert {t.ticket for t in losing} == {2, 3}

    updated = repo.save_review(2, note="Entered against the trend", reviewed_by="op")
    assert updated is not None
    assert updated.reviewed is True
    assert updated.review_note == "Entered against the trend"
    assert updated.reviewed_by == "op"
    assert updated.reviewed_at is not None

    # only_unreviewed now excludes ticket 2.
    assert {t.ticket for t in repo.list_losing(only_unreviewed=True)} == {3}


def test_save_review_unknown_ticket_returns_none(session):
    assert ClosedTradeRepository(session).save_review(
        999, note="x", reviewed_by="op"
    ) is None


def test_mock_closed_trades_range_filters_by_close_time(make_settings):
    from datetime import timedelta

    from app.bridge.mock_bridge import MockBridge

    now = datetime.now(timezone.utc)
    bridge = MockBridge(settings=make_settings(), closed_trades=[
        _trade(1, 10.0),  # close_time ~now (within range)
        ClosedTrade(ticket=2, symbol="XAUUSD", profit=5.0,
                    close_time=now - timedelta(days=10)),  # outside a 3-day window
    ])
    recent = bridge.closed_trades_range(now - timedelta(days=3), now + timedelta(minutes=1))
    assert {t.ticket for t in recent} == {1}


def test_upsert_captures_journal_snapshot(session):
    order = OrderRepository(session).create(
        OrderRequest(
            symbol="XAUUSD", side=OrderSide.SELL, volume=0.2, sl=2360.0,
            risk_pct=1.0, idempotency_key="journal-001",
            strategy_reason="D40 breakout short", ai_reason="momentum fading",
        ),
        state=OrderState.FILLED.value, decision="WARN",
        account_type="DEMO", trading_mode="MANUAL_ONLY",
    )
    order.order_ticket = 700700
    order.planned_risk_amount = 40.0
    session.flush()

    trade = ClosedTrade(
        ticket=700700, symbol="XAUUSD", profit=-40.0,
        close_time=datetime.now(timezone.utc),
        side=OrderSide.SELL, volume=0.2, entry_price=2350.0, exit_price=2360.0,
        open_time=datetime.now(timezone.utc), exit_reason="sl",
    )
    repo = ClosedTradeRepository(session)
    repo.upsert_from_bridge([trade], {700700: order})
    row = repo.get_by_ticket(700700)
    assert row.entry_price == 2350.0
    assert row.exit_price == 2360.0
    assert row.exit_reason == "sl"
    assert row.side == "SELL"
    assert row.r_multiple == -1.0  # -40 / 40
    assert row.strategy_reason == "D40 breakout short"
    assert row.ai_reason == "momentum fading"
    assert row.decision == "WARN"


def test_workflow_persists_closed_trades(session, make_settings):
    settings = make_settings()
    bridge = MockBridge(settings=settings, closed_trades=[_trade(1, 12.0)])
    summary = WorkflowRunner(bridge=bridge, settings=settings).run_once(session)
    assert summary["closed_trades_synced"] == 1
    assert len(ClosedTradeRepository(session).list_recent()) == 1
