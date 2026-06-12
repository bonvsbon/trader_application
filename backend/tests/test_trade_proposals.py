from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.bridge.mock_bridge import MockBridge
from app.core.enums import OrderSide, OrderState
from app.domain.models import NewsRisk, StrategyPresetConfig, VolatilityRisk
from app.execution.order_service import OrderService
from app.news.base import MockNewsProvider
from app.persistence.repositories import (
    AuditRepository,
    StrategyConfigRepository,
    TradeProposalRepository,
)
from app.strategy.proposals import ProposalError, ProposalService


class _LiveNewsProvider:
    name = "test-live"

    def news_risk(self, symbol: str) -> NewsRisk:
        return NewsRisk(provider=self.name, is_live=True, summary="Calendar clear")


class _LiveVolatilityProvider:
    name = "test-live"

    def volatility_risk(self, symbol: str) -> VolatilityRisk:
        return VolatilityRisk(provider=self.name, is_live=True, summary="Volatility normal")


def _service(session, make_settings):
    settings = make_settings()
    bridge = MockBridge(settings=settings)
    return OrderService(
        session,
        bridge,
        settings=settings,
        news_provider=_LiveNewsProvider(),
        volatility_provider=_LiveVolatilityProvider(),
    )


def test_enabled_preset_generates_sized_2r_proposal_and_submits(
    session,
    make_settings,
):
    order_service = _service(session, make_settings)
    StrategyConfigRepository(session).save(
        StrategyPresetConfig(enabled=True),
        updated_by="tester",
    )
    proposals = ProposalService(order_service)

    row = proposals.generate(
        side=OrderSide.BUY,
        sl=2349.0,
        volume=None,
        strategy_reason="Manual D40/D20 setup confirmed by operator",
        created_by="tester",
    )

    assert row.status == "DRAFT"
    assert row.tp == pytest.approx(row.entry_price + 2 * (row.entry_price - row.sl))
    assert row.volume == pytest.approx(0.9)
    assert row.risk_decision == "ALLOW"

    result = proposals.submit(row.id, submitted_by="tester")

    assert result.state is OrderState.FILLED
    assert TradeProposalRepository(session).get(row.id).status == "FILLED"
    events = [item.event for item in AuditRepository(session).list_recent()]
    assert "proposal.generated" in events
    assert "proposal.submitted" in events


def test_disabled_preset_cannot_generate_proposal(session, make_settings):
    proposals = ProposalService(_service(session, make_settings))

    with pytest.raises(ProposalError, match="disabled"):
        proposals.generate(
            side=OrderSide.BUY,
            sl=2349.0,
            volume=0.1,
            strategy_reason="Manual setup",
            created_by="tester",
        )


def test_news_clear_strategy_blocks_proposal_when_provider_is_mock(
    session,
    make_settings,
):
    settings = make_settings()
    order_service = OrderService(
        session,
        MockBridge(settings=settings),
        settings=settings,
        news_provider=MockNewsProvider(),
        volatility_provider=_LiveVolatilityProvider(),
    )
    StrategyConfigRepository(session).save(
        StrategyPresetConfig(enabled=True, require_news_clear=True),
        updated_by="tester",
    )

    row = ProposalService(order_service).generate(
        side=OrderSide.BUY,
        sl=2349.0,
        volume=0.1,
        strategy_reason="Manual setup with required news clearance",
        created_by="tester",
    )

    assert row.status == "BLOCKED"
    assert any("requires live news clearance" in reason for reason in row.risk_reasons)


def test_expired_proposal_cannot_be_submitted(session, make_settings):
    order_service = _service(session, make_settings)
    StrategyConfigRepository(session).save(
        StrategyPresetConfig(enabled=True),
        updated_by="tester",
    )
    proposals = ProposalService(order_service)
    row = proposals.generate(
        side=OrderSide.SELL,
        sl=2351.0,
        volume=0.1,
        strategy_reason="Manual D40/D20 sell setup",
        created_by="tester",
    )
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.flush()

    with pytest.raises(ProposalError, match="expired"):
        proposals.submit(row.id, submitted_by="tester")

    assert row.status == "EXPIRED"
    assert order_service.orders.list_recent() == []
