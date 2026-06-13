"""Repositories — thin data-access wrappers around a SQLAlchemy Session.

Each repository takes a Session and exposes intent-revealing methods. Services
own transaction boundaries (the session is committed by `get_db`/`session_scope`).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import AccountType
from app.domain.models import (
    ClosedTrade,
    Mt5RuntimeConfig,
    OrderRequest,
    RiskResult,
    StrategyPresetConfig,
)
from app.persistence.entities import (
    AnalysisProviderRow,
    AnalysisSnapshotRow,
    AuditLogRow,
    ClosedTradeRow,
    LogRow,
    MarketDataConfigRow,
    Mt5AccountRow,
    Mt5ConfigRow,
    OrderRow,
    PositionRow,
    RiskDecisionRow,
    StrategyConfigRow,
    TradeProposalRow,
    UserRow,
    UserSessionRow,
    WorkflowRunRow,
)
from app.providers.models import AnalysisProviderConfig
from app.market_data.models import MarketDataConfig


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(UserRow)) or 0

    def get(self, user_id: int) -> UserRow | None:
        return self.session.get(UserRow, user_id)

    def get_by_mt5_login(self, mt5_login: int) -> UserRow | None:
        return self.session.scalar(
            select(UserRow).where(UserRow.mt5_login == mt5_login)
        )

    def create(
        self,
        *,
        mt5_login: int,
        display_name: str,
        password_hash: str,
        is_admin: bool,
    ) -> UserRow:
        row = UserRow(
            mt5_login=mt5_login,
            display_name=display_name,
            password_hash=password_hash,
            is_admin=is_admin,
            status="ACTIVE",
        )
        self.session.add(row)
        self.session.flush()
        return row


class Mt5AccountRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def normalize_server(server: str) -> str:
        return server.strip().casefold()

    def get(self, account_id: int) -> Mt5AccountRow | None:
        return self.session.get(Mt5AccountRow, account_id)

    def get_primary_for_user(self, user_id: int) -> Mt5AccountRow | None:
        return self.session.scalar(
            select(Mt5AccountRow)
            .where(
                Mt5AccountRow.owner_user_id == user_id,
                Mt5AccountRow.enabled.is_(True),
            )
            .order_by(Mt5AccountRow.id)
        )

    def create(
        self,
        *,
        owner_user_id: int,
        login: int,
        server: str,
        account_type: str,
        display_name: str,
    ) -> Mt5AccountRow:
        row = Mt5AccountRow(
            owner_user_id=owner_user_id,
            login=login,
            server=server.strip(),
            server_normalized=self.normalize_server(server),
            account_type=account_type,
            display_name=display_name.strip(),
            enabled=True,
        )
        self.session.add(row)
        self.session.flush()
        return row


class UserSessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, token_hash: str) -> UserSessionRow | None:
        return self.session.get(UserSessionRow, token_hash)

    def create(
        self,
        *,
        token_hash: str,
        user_id: int,
        csrf_hash: str,
        expires_at: datetime,
    ) -> UserSessionRow:
        row = UserSessionRow(
            token_hash=token_hash,
            user_id=user_id,
            csrf_hash=csrf_hash,
            expires_at=expires_at,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def revoke(self, token_hash: str) -> None:
        row = self.get(token_hash)
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(timezone.utc)
            self.session.flush()


class OrderRepository:
    def __init__(self, session: Session, mt5_account_id: int = 1) -> None:
        self.session = session
        self.mt5_account_id = mt5_account_id

    def get_by_key(self, idempotency_key: str) -> OrderRow | None:
        return self.session.scalar(
            select(OrderRow).where(
                OrderRow.mt5_account_id == self.mt5_account_id,
                OrderRow.idempotency_key == idempotency_key,
            )
        )

    def create(self, req: OrderRequest, *, state: str, decision: str,
               account_type: str, trading_mode: str,
               dedupe_fingerprint: str | None = None) -> OrderRow:
        row = OrderRow(
            mt5_account_id=self.mt5_account_id,
            idempotency_key=req.idempotency_key,
            dedupe_fingerprint=dedupe_fingerprint,
            symbol=req.symbol,
            side=req.side.value,
            volume=req.volume,
            sl=req.sl,
            tp=req.tp,
            risk_pct=req.risk_pct,
            source=req.source,
            state=state,
            decision=decision,
            account_type=account_type,
            trading_mode=trading_mode,
            strategy_reason=req.strategy_reason,
            ai_reason=req.ai_reason,
            requested_by=req.requested_by,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def reserve(
        self,
        req: OrderRequest,
        *,
        state: str,
        decision: str,
        account_type: str,
        trading_mode: str,
        dedupe_fingerprint: str,
    ) -> tuple[OrderRow | None, OrderRow | None]:
        """Claim an order key/fingerprint atomically.

        Returns `(created, conflict)`. The database unique constraints serialize
        concurrent submissions even when both requests pass the initial reads.
        """
        try:
            with self.session.begin_nested():
                row = self.create(
                    req,
                    state=state,
                    decision=decision,
                    account_type=account_type,
                    trading_mode=trading_mode,
                    dedupe_fingerprint=dedupe_fingerprint,
                )
            return row, None
        except IntegrityError:
            conflict = self.get_by_key(req.idempotency_key)
            if conflict is None:
                conflict = self.session.scalar(
                    select(OrderRow).where(
                        OrderRow.mt5_account_id == self.mt5_account_id,
                        OrderRow.dedupe_fingerprint == dedupe_fingerprint
                    )
                )
            return None, conflict

    def update_state(self, row: OrderRow, *, state: str, decision: str | None = None,
                     order_ticket: int | None = None, message: str | None = None) -> OrderRow:
        row.state = state
        if decision is not None:
            row.decision = decision
        if order_ticket is not None:
            row.order_ticket = order_ticket
        if message is not None:
            row.message = message
        self.session.flush()
        return row

    def update_decision_context(
        self,
        row: OrderRow,
        *,
        decision: str,
        account_type: str,
        trading_mode: str,
        planned_risk_amount: float | None = None,
    ) -> OrderRow:
        row.decision = decision
        row.account_type = account_type
        row.trading_mode = trading_mode
        if planned_risk_amount is not None:
            row.planned_risk_amount = planned_risk_amount
        self.session.flush()
        return row

    def list_filled_with_ticket(self, limit: int = 1000) -> list[OrderRow]:
        """Filled/submitted orders that carry a broker ticket, for matching
        closed trades back to their planned risk."""
        return list(
            self.session.scalars(
                select(OrderRow)
                .where(
                    OrderRow.mt5_account_id == self.mt5_account_id,
                    OrderRow.order_ticket.is_not(None),
                )
                .order_by(OrderRow.id.desc())
                .limit(limit)
            )
        )

    def claim_state(self, row_id: int, *, expected: str, new: str) -> bool:
        result = self.session.execute(
            update(OrderRow)
            .where(
                OrderRow.id == row_id,
                OrderRow.mt5_account_id == self.mt5_account_id,
                OrderRow.state == expected,
            )
            .values(state=new)
            .execution_options(synchronize_session=False)
        )
        self.session.flush()
        return result.rowcount == 1

    def count_today(self) -> int:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return self.session.scalar(
            select(func.count())
            .select_from(OrderRow)
            .where(OrderRow.mt5_account_id == self.mt5_account_id)
            .where(OrderRow.created_at >= start)
            .where(OrderRow.state.in_(["SUBMITTED", "FILLED", "APPROVED", "PENDING_APPROVAL"]))
        ) or 0

    def list_recent(self, limit: int = 50) -> list[OrderRow]:
        return list(
            self.session.scalars(
                select(OrderRow)
                .where(OrderRow.mt5_account_id == self.mt5_account_id)
                .order_by(OrderRow.id.desc())
                .limit(limit)
            )
        )

    def list_reconciliation_pending(self, limit: int = 20) -> list[OrderRow]:
        return list(
            self.session.scalars(
                select(OrderRow)
                .where(
                    OrderRow.mt5_account_id == self.mt5_account_id,
                    OrderRow.state.in_(["SUBMITTED", "RECONCILIATION_REQUIRED"]),
                )
                .order_by(OrderRow.id)
                .limit(limit)
            )
        )

    def list_pending_approval(self, limit: int = 50) -> list[OrderRow]:
        return list(
            self.session.scalars(
                select(OrderRow)
                .where(
                    OrderRow.mt5_account_id == self.mt5_account_id,
                    OrderRow.state == "PENDING_APPROVAL",
                )
                .order_by(OrderRow.created_at)
                .limit(limit)
            )
        )

    def list_expired_pending_approval(
        self,
        *,
        expiry_minutes: int,
        limit: int = 100,
    ) -> list[OrderRow]:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=expiry_minutes)
        return list(
            self.session.scalars(
                select(OrderRow)
                .where(
                    OrderRow.mt5_account_id == self.mt5_account_id,
                    OrderRow.state == "PENDING_APPROVAL",
                )
                .where(OrderRow.created_at <= cutoff)
                .order_by(OrderRow.created_at)
                .limit(limit)
            )
        )

    def has_recent_similar(self, *, symbol: str, side: str, volume: float,
                           within_seconds: int, exclude_key: str) -> bool:
        """Detect a near-identical order placed moments ago under a *different*
        idempotency key — a likely accidental double-submit (safety rule 9)."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=within_seconds)
        count = self.session.scalar(
            select(func.count())
            .select_from(OrderRow)
            .where(OrderRow.mt5_account_id == self.mt5_account_id)
            .where(OrderRow.symbol == symbol)
            .where(OrderRow.side == side)
            .where(OrderRow.volume == volume)
            .where(OrderRow.created_at >= cutoff)
            .where(OrderRow.idempotency_key != exclude_key)
            .where(OrderRow.state.in_(["SUBMITTED", "FILLED", "APPROVED", "PENDING_APPROVAL"]))
        )
        return (count or 0) > 0


class RiskRepository:
    def __init__(self, session: Session, mt5_account_id: int = 1) -> None:
        self.session = session
        self.mt5_account_id = mt5_account_id

    def record(self, symbol: str, result: RiskResult, idempotency_key: str | None) -> RiskDecisionRow:
        row = RiskDecisionRow(
            mt5_account_id=self.mt5_account_id,
            idempotency_key=idempotency_key,
            symbol=symbol,
            decision=result.decision.value,
            reasons=list(result.reasons),
            warnings=list(result.warnings),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def list_recent(self, limit: int = 50) -> list[RiskDecisionRow]:
        return list(
            self.session.scalars(
                select(RiskDecisionRow).order_by(RiskDecisionRow.id.desc()).limit(limit)
                .where(RiskDecisionRow.mt5_account_id == self.mt5_account_id)
            )
        )

    def latest_for(self, idempotency_key: str) -> RiskDecisionRow | None:
        """Most recent risk decision recorded for an order key.

        Used to surface the actual ALLOW/WARN/BLOCK reasons in the approval
        queue so an operator approves with the risk context in view.
        """
        return self.session.scalar(
            select(RiskDecisionRow)
            .where(
                RiskDecisionRow.mt5_account_id == self.mt5_account_id,
                RiskDecisionRow.idempotency_key == idempotency_key,
            )
            .order_by(RiskDecisionRow.id.desc())
        )


class AuditRepository:
    def __init__(self, session: Session, mt5_account_id: int = 1) -> None:
        self.session = session
        self.mt5_account_id = mt5_account_id

    def write(self, *, event: str, idempotency_key: str | None = None, order_id: int | None = None,
              symbol: str | None = None, account_type: str | None = None,
              trading_mode: str | None = None, decision: str | None = None,
              strategy_reason: str | None = None, ai_reason: str | None = None,
              user_approval: bool | None = None, mt5_response: dict | None = None,
              payload: dict | None = None) -> AuditLogRow:
        row = AuditLogRow(
            mt5_account_id=self.mt5_account_id,
            event=event,
            idempotency_key=idempotency_key,
            order_id=order_id,
            symbol=symbol,
            account_type=account_type,
            trading_mode=trading_mode,
            decision=decision,
            strategy_reason=strategy_reason,
            ai_reason=ai_reason,
            user_approval=user_approval,
            mt5_response=mt5_response,
            payload=payload,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def list_recent(self, limit: int = 100) -> list[AuditLogRow]:
        return list(
            self.session.scalars(
                select(AuditLogRow)
                .where(AuditLogRow.mt5_account_id == self.mt5_account_id)
                .order_by(AuditLogRow.id.desc())
                .limit(limit)
            )
        )

    def has_event(self, order_id: int, event: str) -> bool:
        count = self.session.scalar(
            select(func.count())
            .select_from(AuditLogRow)
            .where(
                AuditLogRow.mt5_account_id == self.mt5_account_id,
                AuditLogRow.order_id == order_id,
                AuditLogRow.event == event,
            )
        )
        return (count or 0) > 0


class LogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, level: str, source: str, message: str, context: dict | None = None) -> LogRow:
        row = LogRow(level=level, source=source, message=message, context=context)
        self.session.add(row)
        self.session.flush()
        return row

    def list_recent(self, limit: int = 100) -> list[LogRow]:
        return list(
            self.session.scalars(select(LogRow).order_by(LogRow.id.desc()).limit(limit))
        )


class WorkflowRepository:
    def __init__(self, session: Session, mt5_account_id: int = 1) -> None:
        self.session = session
        self.mt5_account_id = mt5_account_id

    def start(self, step: str = "init") -> WorkflowRunRow:
        row = WorkflowRunRow(
            mt5_account_id=self.mt5_account_id, step=step, status="running"
        )
        self.session.add(row)
        self.session.flush()
        return row

    def finish(self, row: WorkflowRunRow, *, status: str, step: str,
               detail: dict | None = None, error: str | None = None) -> WorkflowRunRow:
        from app.persistence.entities import utcnow

        row.finished_at = utcnow()
        row.status = status
        row.step = step
        row.detail = detail
        row.error = error
        self.session.flush()
        return row

    def list_recent(self, limit: int = 20) -> list[WorkflowRunRow]:
        return list(
            self.session.scalars(
                select(WorkflowRunRow)
                .where(WorkflowRunRow.mt5_account_id == self.mt5_account_id)
                .order_by(WorkflowRunRow.id.desc())
                .limit(limit)
            )
        )


class PositionRepository:
    def __init__(self, session: Session, mt5_account_id: int = 1) -> None:
        self.session = session
        self.mt5_account_id = mt5_account_id

    def count_open(self) -> int:
        # Phase 1: positions are synced as snapshots; count the latest sync batch.
        recent = datetime.now(timezone.utc) - timedelta(minutes=10)
        return self.session.scalar(
            select(func.count())
            .select_from(PositionRow)
            .where(
                PositionRow.mt5_account_id == self.mt5_account_id,
                PositionRow.synced_at >= recent,
            )
        ) or 0


class Mt5ConfigRepository:
    def __init__(self, session: Session, mt5_account_id: int = 1) -> None:
        self.session = session
        self.mt5_account_id = mt5_account_id

    def get(self) -> Mt5ConfigRow | None:
        return self.session.scalar(
            select(Mt5ConfigRow).where(
                Mt5ConfigRow.mt5_account_id == self.mt5_account_id
            )
        )

    def get_config(self) -> Mt5RuntimeConfig | None:
        row = self.get()
        if row is None:
            return None
        return Mt5RuntimeConfig(
            enabled=row.enabled,
            bridge_type=row.bridge_type,
            host=row.host,
            port=row.port,
            timeout_sec=row.timeout_sec,
            heartbeat_max_age_sec=row.heartbeat_max_age_sec,
            expected_login=row.expected_login,
            expected_server=row.expected_server,
            expected_account_type=AccountType(row.expected_account_type),
        )

    def save(self, config: Mt5RuntimeConfig, *, updated_by: str) -> Mt5ConfigRow:
        row = self.get()
        if row is None:
            row = Mt5ConfigRow(mt5_account_id=self.mt5_account_id)
            self.session.add(row)
        row.enabled = config.enabled
        row.bridge_type = config.bridge_type
        row.host = config.host
        row.port = config.port
        row.timeout_sec = config.timeout_sec
        row.heartbeat_max_age_sec = config.heartbeat_max_age_sec
        row.expected_login = config.expected_login
        row.expected_server = config.expected_server
        row.expected_account_type = config.expected_account_type.value
        row.updated_by = updated_by
        self.session.flush()
        return row

    def bind_account(self, account_id: int) -> Mt5ConfigRow:
        self.mt5_account_id = account_id
        row = self.get()
        if row is None:
            row = Mt5ConfigRow(mt5_account_id=account_id)
            self.session.add(row)
        self.session.flush()
        return row


class StrategyConfigRepository:
    def __init__(self, session: Session, mt5_account_id: int = 1) -> None:
        self.session = session
        self.mt5_account_id = mt5_account_id

    def get(self) -> StrategyConfigRow | None:
        return self.session.scalar(
            select(StrategyConfigRow).where(
                StrategyConfigRow.mt5_account_id == self.mt5_account_id
            )
        )

    def get_config(self) -> StrategyPresetConfig | None:
        row = self.get()
        if row is None:
            return None
        return StrategyPresetConfig(
            enabled=row.enabled,
            symbol=row.symbol,
            preset_name=row.preset_name,
            d40_value=row.d40_value,
            d20_value=row.d20_value,
            reward_risk_ratio=row.reward_risk_ratio,
            risk_pct=row.risk_pct,
            require_news_clear=row.require_news_clear,
            signal_definition_confirmed=row.signal_definition_confirmed,
        )

    def save(
        self,
        config: StrategyPresetConfig,
        *,
        updated_by: str,
    ) -> StrategyConfigRow:
        row = self.get()
        if row is None:
            row = StrategyConfigRow(mt5_account_id=self.mt5_account_id)
            self.session.add(row)
        for field, value in config.model_dump().items():
            setattr(row, field, value)
        row.health = "UNKNOWN"
        row.latency_ms = None
        row.discovered_tools = []
        row.last_checked_at = None
        row.last_error = None
        row.updated_by = updated_by
        self.session.flush()
        return row


class AnalysisProviderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, provider_id: int) -> AnalysisProviderRow | None:
        return self.session.get(AnalysisProviderRow, provider_id)

    def get_by_name(self, display_name: str) -> AnalysisProviderRow | None:
        return self.session.scalar(
            select(AnalysisProviderRow).where(
                func.lower(AnalysisProviderRow.display_name) == display_name.lower()
            )
        )

    def list_all(self) -> list[AnalysisProviderRow]:
        return list(
            self.session.scalars(
                select(AnalysisProviderRow).order_by(
                    AnalysisProviderRow.priority,
                    AnalysisProviderRow.id,
                )
            )
        )

    def save(
        self,
        config: AnalysisProviderConfig,
        *,
        updated_by: str,
        row: AnalysisProviderRow | None = None,
    ) -> AnalysisProviderRow:
        row = row or AnalysisProviderRow()
        if row.id is None:
            self.session.add(row)
        for field, value in config.model_dump().items():
            setattr(row, field, value)
        row.updated_by = updated_by
        self.session.flush()
        return row

    def record_health(
        self,
        row: AnalysisProviderRow,
        *,
        health: str,
        latency_ms: float | None,
        discovered_tools: list[dict],
        error: str | None,
        discovered_models: list[str] | None = None,
    ) -> AnalysisProviderRow:
        from app.persistence.entities import utcnow

        row.health = health
        row.latency_ms = latency_ms
        row.discovered_tools = discovered_tools
        row.discovered_models = discovered_models or []
        row.last_error = error
        row.last_checked_at = utcnow()
        self.session.flush()
        return row

    def delete(self, row: AnalysisProviderRow) -> None:
        self.session.delete(row)
        self.session.flush()


class AnalysisSnapshotRepository:
    def __init__(self, session: Session, mt5_account_id: int = 1) -> None:
        self.session = session
        self.mt5_account_id = mt5_account_id

    def record(self, **values) -> AnalysisSnapshotRow:
        row = AnalysisSnapshotRow(mt5_account_id=self.mt5_account_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def list_recent(self, limit: int = 100) -> list[AnalysisSnapshotRow]:
        return list(
            self.session.scalars(
                select(AnalysisSnapshotRow)
                .where(
                    AnalysisSnapshotRow.mt5_account_id == self.mt5_account_id
                )
                .order_by(AnalysisSnapshotRow.id.desc())
                .limit(limit)
            )
        )


class MarketDataConfigRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self) -> MarketDataConfigRow | None:
        return self.session.get(MarketDataConfigRow, 1)

    def get_config(self) -> MarketDataConfig | None:
        row = self.get()
        if row is None:
            return None
        return MarketDataConfig(
            enabled=row.enabled,
            provider=row.provider,
            endpoint=row.endpoint,
            feed=row.feed,
            api_key_ref=row.api_key_ref,
            api_secret_ref=row.api_secret_ref,
            default_symbols=row.default_symbols or [],
            max_symbols=row.max_symbols,
            timeout_sec=row.timeout_sec,
        )

    def save(self, config: MarketDataConfig, *, updated_by: str) -> MarketDataConfigRow:
        row = self.get()
        if row is None:
            row = MarketDataConfigRow(id=1)
            self.session.add(row)
        for field, value in config.model_dump().items():
            setattr(row, field, value)
        row.updated_by = updated_by
        self.session.flush()
        return row


class TradeProposalRepository:
    def __init__(self, session: Session, mt5_account_id: int = 1) -> None:
        self.session = session
        self.mt5_account_id = mt5_account_id

    def get(self, proposal_id: int) -> TradeProposalRow | None:
        return self.session.scalar(
            select(TradeProposalRow).where(
                TradeProposalRow.id == proposal_id,
                TradeProposalRow.mt5_account_id == self.mt5_account_id,
            )
        )

    def create(self, **values) -> TradeProposalRow:
        row = TradeProposalRow(mt5_account_id=self.mt5_account_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def list_recent(self, limit: int = 50) -> list[TradeProposalRow]:
        return list(
            self.session.scalars(
                select(TradeProposalRow)
                .where(TradeProposalRow.mt5_account_id == self.mt5_account_id)
                .order_by(TradeProposalRow.id.desc())
                .limit(limit)
            )
        )

    def get_by_order_key(self, order_idempotency_key: str) -> TradeProposalRow | None:
        """Resolve the proposal that produced a given order, if any.

        A submitted proposal stamps its `order_idempotency_key` with the order's
        key, so the approval queue can show the originating strategy/AI context.
        """
        return self.session.scalar(
            select(TradeProposalRow).where(
                TradeProposalRow.mt5_account_id == self.mt5_account_id,
                TradeProposalRow.order_idempotency_key == order_idempotency_key
            )
        )

    def update_status(
        self,
        row: TradeProposalRow,
        status: str,
        *,
        order_idempotency_key: str | None = None,
    ) -> TradeProposalRow:
        row.status = status
        if order_idempotency_key is not None:
            row.order_idempotency_key = order_idempotency_key
        self.session.flush()
        return row


class ClosedTradeRepository:
    def __init__(self, session: Session, mt5_account_id: int = 1) -> None:
        self.session = session
        self.mt5_account_id = mt5_account_id

    def _existing_tickets(self) -> set[int]:
        return set(
            self.session.scalars(
                select(ClosedTradeRow.ticket).where(
                    ClosedTradeRow.mt5_account_id == self.mt5_account_id
                )
            )
        )

    def upsert_from_bridge(
        self,
        trades: list[ClosedTrade],
        order_by_ticket: dict[int, OrderRow] | None = None,
    ) -> int:
        """Persist closed trades not seen before (dedupe by ticket).

        Returns the number of newly inserted rows. Matching to one of our orders
        by ticket lets us copy the planned risk and compute the realized
        R-multiple. Trades with no matching order are still recorded.
        """
        order_by_ticket = order_by_ticket or {}
        existing = self._existing_tickets()
        inserted = 0
        for trade in trades:
            if trade.ticket in existing:
                continue
            order = order_by_ticket.get(trade.ticket)
            planned_risk = order.planned_risk_amount if order is not None else None
            r_multiple = None
            if planned_risk is not None and planned_risk > 0:
                r_multiple = trade.profit / planned_risk
            # Prefer the broker-reported side/volume; fall back to our order.
            side = trade.side.value if trade.side is not None else (
                order.side if order is not None else None
            )
            volume = trade.volume if trade.volume is not None else (
                order.volume if order is not None else None
            )
            self.session.add(
                ClosedTradeRow(
                    mt5_account_id=self.mt5_account_id,
                    ticket=trade.ticket,
                    symbol=trade.symbol,
                    side=side,
                    volume=volume,
                    profit=trade.profit,
                    close_time=trade.close_time,
                    matched_order_id=order.id if order is not None else None,
                    planned_risk_amount=planned_risk,
                    r_multiple=r_multiple,
                    entry_price=trade.entry_price,
                    exit_price=trade.exit_price,
                    open_time=trade.open_time,
                    exit_reason=trade.exit_reason,
                    strategy_reason=order.strategy_reason if order is not None else None,
                    ai_reason=order.ai_reason if order is not None else None,
                    decision=order.decision if order is not None else None,
                )
            )
            existing.add(trade.ticket)
            inserted += 1
        self.session.flush()
        return inserted

    def list_recent(self, limit: int = 100) -> list[ClosedTradeRow]:
        return list(
            self.session.scalars(
                select(ClosedTradeRow).order_by(ClosedTradeRow.id.desc()).limit(limit)
                .where(ClosedTradeRow.mt5_account_id == self.mt5_account_id)
            )
        )

    def get_by_ticket(self, ticket: int) -> ClosedTradeRow | None:
        return self.session.scalar(
            select(ClosedTradeRow).where(ClosedTradeRow.ticket == ticket)
            .where(ClosedTradeRow.mt5_account_id == self.mt5_account_id)
        )

    def list_losing(self, limit: int = 100, *, only_unreviewed: bool = False) -> list[ClosedTradeRow]:
        """Losing closed trades (profit < 0), newest first — the review queue."""
        stmt = select(ClosedTradeRow).where(
            ClosedTradeRow.mt5_account_id == self.mt5_account_id,
            ClosedTradeRow.profit < 0,
        )
        if only_unreviewed:
            stmt = stmt.where(ClosedTradeRow.reviewed.is_(False))
        return list(
            self.session.scalars(stmt.order_by(ClosedTradeRow.id.desc()).limit(limit))
        )

    def save_review(self, ticket: int, *, note: str, reviewed_by: str) -> ClosedTradeRow | None:
        row = self.get_by_ticket(ticket)
        if row is None:
            return None
        row.review_note = note
        row.reviewed = True
        row.reviewed_by = reviewed_by
        from app.persistence.entities import utcnow

        row.reviewed_at = utcnow()
        self.session.flush()
        return row

    @staticmethod
    def _aggregate(rows: list[ClosedTradeRow]) -> dict:
        total = len(rows)
        wins = sum(1 for r in rows if r.profit > 0)
        losses = sum(1 for r in rows if r.profit < 0)
        net_pnl = sum(r.profit for r in rows)
        gross_profit = sum(r.profit for r in rows if r.profit > 0)
        gross_loss = sum(r.profit for r in rows if r.profit < 0)
        r_values = [r.r_multiple for r in rows if r.r_multiple is not None]
        total_r = sum(r_values)
        return {
            "count": total,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": (wins / total * 100.0) if total else None,
            "net_pnl": net_pnl,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "total_r": total_r if r_values else None,
            "avg_r": (total_r / len(r_values)) if r_values else None,
            "rated_count": len(r_values),
        }

    def summary(self) -> dict:
        return self._aggregate(
            list(
                self.session.scalars(
                    select(ClosedTradeRow).where(
                        ClosedTradeRow.mt5_account_id == self.mt5_account_id
                    )
                )
            )
        )

    def daily_breakdown(self, limit_days: int = 30) -> list[dict]:
        """Closed trades grouped by close day (newest first), each with its own
        P&L/R aggregate. Trades without a close time fall back to sync time."""
        rows = list(
            self.session.scalars(
                select(ClosedTradeRow).where(
                    ClosedTradeRow.mt5_account_id == self.mt5_account_id
                )
            )
        )
        buckets: dict[str, list[ClosedTradeRow]] = {}
        for r in rows:
            ts = r.close_time or r.synced_at
            day = ts.date().isoformat() if ts is not None else "unknown"
            buckets.setdefault(day, []).append(r)
        out: list[dict] = []
        for day in sorted(buckets, reverse=True)[:limit_days]:
            out.append({"date": day, **self._aggregate(buckets[day])})
        return out
