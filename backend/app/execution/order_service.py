"""The order chokepoint.

EVERY order — manual or automated — goes through `OrderService.place_order`.
Nothing else in the codebase may call `bridge.execute_order`. The enforced
sequence (safety rules M.1–M.10 + rule.md):

    1. duplicate idempotency key      -> return prior result (no new order)
    2. suspected accidental duplicate -> BLOCK
    3. gather context (bridge health, account, quote, counts, news, config)
    4. RiskEngine.evaluate            -> BLOCK => RISK_BLOCKED (persist + audit)
    5. real account / WARN            -> PENDING_APPROVAL (no execution)
    6. ALLOW + demo/full-auto         -> execute via bridge
    7. always write an audit log with the full decision context

Approval (`approve_order`) re-evaluates risk before executing, because market
conditions may have changed while the order sat in the queue.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import Settings, get_settings
from app.core.enums import AccountType, BridgeHealth, OrderSide, OrderState, RiskDecision, TradingMode
from app.core.logging import get_logger
from app.domain.models import (
    AccountInfo,
    NewsRisk,
    OrderRequest,
    OrderResult,
    RiskContext,
    RiskResult,
    VolatilityRisk,
)
from app.domain.ports import MT5BridgePort, NewsProviderPort, VolatilityProviderPort
from app.execution import state_machine
from app.execution.idempotency import DUPLICATE_WINDOW_SECONDS, make_duplicate_fingerprint
from app.persistence.entities import OrderRow
from app.persistence.repositories import (
    AuditRepository,
    LogRepository,
    OrderRepository,
    RiskRepository,
)
from app.risk.engine import RiskEngine
from app.risk.sizing import calculate_position_sizing, position_risk_amount

logger = get_logger(__name__)

MT5_RETCODE_PLACED = 10008
MT5_RETCODE_DONE = 10009
MT5_RETCODE_DONE_PARTIAL = 10010


class OrderService:
    def __init__(
        self,
        session,
        bridge: MT5BridgePort,
        *,
        settings: Settings | None = None,
        risk_engine: RiskEngine | None = None,
        news_provider: NewsProviderPort | None = None,
        volatility_provider: VolatilityProviderPort | None = None,
    ) -> None:
        self.session = session
        self.bridge = bridge
        self.settings = settings or get_settings()
        self.risk_engine = risk_engine or RiskEngine(self.settings)
        self.news_provider = news_provider
        self.volatility_provider = volatility_provider
        self.orders = OrderRepository(session)
        self.audit = AuditRepository(session)
        self.risk_repo = RiskRepository(session)
        self.logs = LogRepository(session)

    # ── Public API ────────────────────────────────────────────────────────────
    def place_order(self, req: OrderRequest) -> OrderResult:
        # 1. Exact idempotency match: never place a second order for the same key.
        existing = self.orders.get_by_key(req.idempotency_key)
        if existing is not None:
            self.audit.write(
                event="order.duplicate_key",
                idempotency_key=req.idempotency_key,
                order_id=existing.id,
                symbol=existing.symbol,
                payload={"note": "Idempotency key already seen; returning prior result"},
            )
            return self._result_from_row(existing, message="Duplicate idempotency key; prior result returned")

        # 2. Suspected accidental duplicate (same order, different key, moments ago).
        if self.orders.has_recent_similar(
            symbol=req.symbol,
            side=req.side.value,
            volume=req.volume,
            within_seconds=DUPLICATE_WINDOW_SECONDS,
            exclude_key=req.idempotency_key,
        ):
            return self._block_without_context(
                req, reason="Suspected duplicate order (identical order placed moments ago)"
            )

        # 3. Reserve both the idempotency key and near-duplicate fingerprint in
        # the database before gathering context or reaching the broker.
        fingerprint = make_duplicate_fingerprint(req)
        row, conflict = self.orders.reserve(
            req,
            state=OrderState.PENDING.value,
            decision=RiskDecision.BLOCK.value,
            account_type=AccountType.UNKNOWN.value,
            trading_mode=self.settings.trading_mode.value,
            dedupe_fingerprint=fingerprint,
        )
        if row is None:
            if conflict is not None and conflict.idempotency_key == req.idempotency_key:
                self.audit.write(
                    event="order.duplicate_key",
                    idempotency_key=req.idempotency_key,
                    order_id=conflict.id,
                    symbol=conflict.symbol,
                    payload={"note": "Concurrent idempotency key already reserved"},
                )
                return self._result_from_row(
                    conflict, message="Duplicate idempotency key; prior result returned"
                )
            return self._block_without_context(
                req, reason="Suspected concurrent duplicate order"
            )

        # 4. Gather decision context (fail-safe: failures become BLOCK inputs).
        health = self._safe_health()
        account = self._safe_account()
        ctx = self._build_context(req, health, account)

        # 5. Risk decision.
        risk = self.risk_engine.evaluate(ctx)
        self.risk_repo.record(req.symbol, risk, req.idempotency_key)
        planned_risk = abs(ctx.estimated_loss) if ctx.estimated_loss is not None else None
        self.orders.update_decision_context(
            row,
            decision=risk.decision.value,
            account_type=account.account_type.value,
            trading_mode=self.settings.trading_mode.value,
            planned_risk_amount=planned_risk,
        )

        if risk.decision is RiskDecision.BLOCK:
            return self._transition(
                row, OrderState.PENDING, OrderState.RISK_BLOCKED, risk,
                event="order.blocked", message="; ".join(risk.reasons),
            )

        # 6. Approval gate: real accounts and any WARN require a human.
        if self._requires_manual_approval(account.account_type, risk):
            return self._transition(
                row, OrderState.PENDING, OrderState.PENDING_APPROVAL, risk,
                event="order.pending_approval",
                message="Manual approval required before execution",
            )

        # 7. ALLOW + (demo, or fully-automatic real) -> execute.
        return self._execute(row, req, risk, account.account_type)

    def approve_order(self, idempotency_key: str, approved_by: str) -> OrderResult:
        """Confirm a queued order. Re-runs risk before executing."""
        row = self.orders.get_by_key(idempotency_key)
        if row is None:
            raise ValueError(f"No order for idempotency key {idempotency_key!r}")
        if row.state != OrderState.PENDING_APPROVAL.value:
            return self._result_from_row(row, message=f"Order is not awaiting approval (state={row.state})")
        if self._is_older_than(row.created_at, self.settings.approval_expiry_minutes):
            return self._expire_approval(row, expired_by=approved_by)

        req = self._request_from_row(row)
        health = self._safe_health()
        account = self._safe_account()
        risk = self.risk_engine.evaluate(self._build_context(req, health, account))
        self.risk_repo.record(req.symbol, risk, req.idempotency_key)

        if risk.decision is RiskDecision.BLOCK:
            return self._claim_transition(
                row, OrderState.PENDING_APPROVAL, OrderState.RISK_BLOCKED, risk,
                event="order.blocked_on_approval", message="; ".join(risk.reasons),
                user_approval=True,
            )

        state_machine.assert_transition(OrderState.PENDING_APPROVAL, OrderState.APPROVED)
        if not self.orders.claim_state(
            row.id,
            expected=OrderState.PENDING_APPROVAL.value,
            new=OrderState.APPROVED.value,
        ):
            self.session.refresh(row)
            return self._result_from_row(
                row, message=f"Order was already handled (state={row.state})"
            )
        self.session.refresh(row)
        self.audit.write(
            event="order.approved", idempotency_key=row.idempotency_key, order_id=row.id,
            symbol=row.symbol, account_type=row.account_type, trading_mode=row.trading_mode,
            decision=risk.decision.value, strategy_reason=row.strategy_reason,
            ai_reason=row.ai_reason, user_approval=True,
            payload={"approved_by": approved_by},
        )
        return self._execute(row, req, risk, account.account_type, user_approval=True,
                             from_state=OrderState.APPROVED)

    def reject_order(self, idempotency_key: str, rejected_by: str) -> OrderResult:
        row = self.orders.get_by_key(idempotency_key)
        if row is None:
            raise ValueError(f"No order for idempotency key {idempotency_key!r}")
        if row.state != OrderState.PENDING_APPROVAL.value:
            return self._result_from_row(row, message=f"Order is not awaiting approval (state={row.state})")
        state_machine.assert_transition(OrderState.PENDING_APPROVAL, OrderState.CANCELLED)
        if not self.orders.claim_state(
            row.id,
            expected=OrderState.PENDING_APPROVAL.value,
            new=OrderState.CANCELLED.value,
        ):
            self.session.refresh(row)
            return self._result_from_row(
                row, message=f"Order was already handled (state={row.state})"
            )
        self.session.refresh(row)
        self.orders.update_state(
            row, state=OrderState.CANCELLED.value, message=f"Rejected by {rejected_by}"
        )
        self.audit.write(
            event="order.rejected", idempotency_key=row.idempotency_key, order_id=row.id,
            symbol=row.symbol, account_type=row.account_type, trading_mode=row.trading_mode,
            user_approval=False, payload={"rejected_by": rejected_by},
        )
        return self._result_from_row(row, message="Order rejected")

    def expire_pending_approvals(self, expired_by: str = "workflow") -> list[OrderResult]:
        expired: list[OrderResult] = []
        rows = self.orders.list_expired_pending_approval(
            expiry_minutes=self.settings.approval_expiry_minutes
        )
        for row in rows:
            expired.append(self._expire_approval(row, expired_by=expired_by))
        return expired

    def alert_expired_reconciliation(self, row: OrderRow) -> bool:
        if not self._is_older_than(
            row.created_at,
            self.settings.reconciliation_expiry_minutes,
        ):
            return False
        event = "order.reconciliation_expired"
        if self.audit.has_event(row.id, event):
            return False
        age_minutes = self._age_minutes(row.created_at)
        payload = {
            "age_minutes": round(age_minutes, 1),
            "expiry_minutes": self.settings.reconciliation_expiry_minutes,
            "operator_action_required": True,
        }
        self.audit.write(
            event=event,
            idempotency_key=row.idempotency_key,
            order_id=row.id,
            symbol=row.symbol,
            account_type=row.account_type,
            trading_mode=row.trading_mode,
            decision=row.decision,
            payload=payload,
        )
        self.logs.add(
            "ERROR",
            "reconciliation",
            "Order outcome remains uncertain beyond reconciliation expiry",
            {"idempotency_key": row.idempotency_key, **payload},
        )
        return True

    def reconcile_order(self, idempotency_key: str, reconciled_by: str) -> OrderResult:
        row = self.orders.get_by_key(idempotency_key)
        if row is None:
            raise ValueError(f"No order for idempotency key {idempotency_key!r}")
        current = OrderState(row.state)
        if current not in {
            OrderState.SUBMITTED,
            OrderState.RECONCILIATION_REQUIRED,
        }:
            return self._result_from_row(
                row, message=f"Order does not require reconciliation (state={row.state})"
            )
        try:
            response = self.bridge.order_status(idempotency_key)
        except Exception as exc:
            self.audit.write(
                event="order.reconciliation_failed",
                idempotency_key=row.idempotency_key,
                order_id=row.id,
                symbol=row.symbol,
                account_type=row.account_type,
                trading_mode=row.trading_mode,
                decision=row.decision,
                payload={"error": str(exc), "reconciled_by": reconciled_by},
            )
            return self._result_from_row(
                row, message=f"Reconciliation failed; outcome remains uncertain: {exc}"
            )
        if response is None:
            self.audit.write(
                event="order.reconciliation_pending",
                idempotency_key=row.idempotency_key,
                order_id=row.id,
                symbol=row.symbol,
                account_type=row.account_type,
                trading_mode=row.trading_mode,
                decision=row.decision,
                payload={"reconciled_by": reconciled_by},
            )
            return self._result_from_row(
                row, message="Order not found yet; reconciliation still required"
            )
        risk = RiskResult(decision=RiskDecision(row.decision))
        return self._handle_broker_response(
            row,
            risk,
            response,
            user_approval=None,
            from_state=current,
            audit_payload={"reconciled_by": reconciled_by},
        )

    def preview(self, req: OrderRequest) -> tuple[RiskResult, RiskContext]:
        """Evaluate risk for a hypothetical order WITHOUT persisting or executing.

        Powers the Risk Monitor page so it can show the live ALLOW/WARN/BLOCK
        state and the underlying facts.
        """
        health = self._safe_health()
        account = self._safe_account()
        ctx = self._build_context(req, health, account)
        return self.risk_engine.evaluate(ctx), ctx

    def _expire_approval(self, row: OrderRow, *, expired_by: str) -> OrderResult:
        state_machine.assert_transition(OrderState.PENDING_APPROVAL, OrderState.CANCELLED)
        if not self.orders.claim_state(
            row.id,
            expected=OrderState.PENDING_APPROVAL.value,
            new=OrderState.CANCELLED.value,
        ):
            self.session.refresh(row)
            return self._result_from_row(
                row, message=f"Order was already handled (state={row.state})"
            )
        self.session.refresh(row)
        message = "Approval expired; submit a new order using current market data"
        self.orders.update_state(row, state=OrderState.CANCELLED.value, message=message)
        self.audit.write(
            event="order.approval_expired",
            idempotency_key=row.idempotency_key,
            order_id=row.id,
            symbol=row.symbol,
            account_type=row.account_type,
            trading_mode=row.trading_mode,
            decision=row.decision,
            payload={
                "expired_by": expired_by,
                "expiry_minutes": self.settings.approval_expiry_minutes,
            },
        )
        return self._result_from_row(row, message=message)

    @staticmethod
    def _age_minutes(created_at: datetime) -> float:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return max(
            0.0,
            (datetime.now(timezone.utc) - created_at).total_seconds() / 60.0,
        )

    @classmethod
    def _is_older_than(cls, created_at: datetime, minutes: int) -> bool:
        return cls._age_minutes(created_at) >= minutes

    # ── Internals ──────────────────────────────────────────────────────────────
    def _requires_manual_approval(self, account_type: AccountType, risk: RiskResult) -> bool:
        if risk.decision is RiskDecision.WARN:
            return True
        if account_type is AccountType.REAL:
            # Real orders always need a human unless fully-automatic real is
            # explicitly enabled via multiple flags (off by default).
            return not self.settings.auto_real_full_enabled()
        return False

    def _execute(self, row: OrderRow, req: OrderRequest, risk: RiskResult,
                 account_type: AccountType, *, user_approval: bool | None = None,
                 from_state: OrderState = OrderState.PENDING) -> OrderResult:
        state_machine.assert_transition(from_state, OrderState.SUBMITTED)
        self.orders.update_state(row, state=OrderState.SUBMITTED.value)
        self.audit.write(
            event="order.submitted", idempotency_key=row.idempotency_key, order_id=row.id,
            symbol=row.symbol, account_type=row.account_type, trading_mode=row.trading_mode,
            decision=risk.decision.value, strategy_reason=row.strategy_reason,
            ai_reason=row.ai_reason, user_approval=user_approval,
        )
        try:
            mt5_response = self.bridge.execute_order(req)
        except Exception as exc:  # bridge transport failure => safe ERROR, never a silent gap
            logger.exception("Bridge execution failed for %s", row.idempotency_key)
            return self._mark_reconciliation_required(
                row,
                risk,
                f"Bridge result is uncertain and requires reconciliation: {exc}",
            )

        return self._handle_broker_response(
            row,
            risk,
            mt5_response,
            user_approval=user_approval,
            from_state=OrderState.SUBMITTED,
        )

    def _handle_broker_response(
        self,
        row: OrderRow,
        risk: RiskResult,
        mt5_response: dict,
        *,
        user_approval: bool | None,
        from_state: OrderState,
        audit_payload: dict | None = None,
    ) -> OrderResult:

        if not isinstance(mt5_response, dict):
            return self._mark_reconciliation_required(
                row, risk, "Broker returned a malformed non-object response", mt5_response=None
            )

        try:
            retcode = int(mt5_response["retcode"])
        except (KeyError, TypeError, ValueError):
            return self._mark_reconciliation_required(
                row, risk, "Broker response is missing a valid retcode", mt5_response=mt5_response
            )

        ticket = mt5_response.get("ticket")
        successful_retcode = retcode in {
            MT5_RETCODE_PLACED,
            MT5_RETCODE_DONE,
            MT5_RETCODE_DONE_PARTIAL,
        }
        valid_ticket = isinstance(ticket, int) and not isinstance(ticket, bool) and ticket > 0
        if successful_retcode and not valid_ticket:
            return self._mark_reconciliation_required(
                row, risk, "Successful broker response is missing a valid order ticket",
                mt5_response=mt5_response,
            )

        if retcode == MT5_RETCODE_PLACED:
            if from_state is OrderState.RECONCILIATION_REQUIRED:
                state_machine.assert_transition(from_state, OrderState.SUBMITTED)
            self.orders.update_state(
                row, state=OrderState.SUBMITTED.value, order_ticket=ticket,
                message="Accepted by broker; awaiting reconciliation",
            )
            self.audit.write(
                event="order.accepted", idempotency_key=row.idempotency_key, order_id=row.id,
                symbol=row.symbol, account_type=row.account_type, trading_mode=row.trading_mode,
                decision=risk.decision.value, strategy_reason=row.strategy_reason,
                ai_reason=row.ai_reason, user_approval=user_approval, mt5_response=mt5_response,
                payload=audit_payload,
            )
            return self._result(
                row, risk, OrderState.SUBMITTED, mt5_response=mt5_response,
                message="Accepted by broker; awaiting reconciliation",
            )

        if retcode not in {MT5_RETCODE_DONE, MT5_RETCODE_DONE_PARTIAL}:
            message = mt5_response.get("retcode_text") or f"Broker rejected order (retcode={retcode})"
            state_machine.assert_transition(from_state, OrderState.REJECTED)
            self.orders.update_state(row, state=OrderState.REJECTED.value, message=message)
            self.audit.write(
                event="order.broker_rejected", idempotency_key=row.idempotency_key, order_id=row.id,
                symbol=row.symbol, account_type=row.account_type, trading_mode=row.trading_mode,
                decision=risk.decision.value, strategy_reason=row.strategy_reason,
                ai_reason=row.ai_reason, user_approval=user_approval, mt5_response=mt5_response,
                payload=audit_payload,
            )
            return self._result(
                row, risk, OrderState.REJECTED, mt5_response=mt5_response, message=message
            )

        message = "Partially filled" if retcode == MT5_RETCODE_DONE_PARTIAL else "Filled"
        state_machine.assert_transition(from_state, OrderState.FILLED)
        self.orders.update_state(
            row, state=OrderState.FILLED.value, order_ticket=ticket, message=message
        )
        self.audit.write(
            event="order.filled", idempotency_key=row.idempotency_key, order_id=row.id,
            symbol=row.symbol, account_type=row.account_type, trading_mode=row.trading_mode,
            decision=risk.decision.value, strategy_reason=row.strategy_reason,
            ai_reason=row.ai_reason, user_approval=user_approval, mt5_response=mt5_response,
            payload=audit_payload,
        )
        return self._result(
            row, risk, OrderState.FILLED, mt5_response=mt5_response, message=message
        )

    def _build_context(self, req: OrderRequest, health: BridgeHealth, account: AccountInfo) -> RiskContext:
        quote = None
        symbol_info = None
        data_problems: list[str] = []
        try:
            quote = self.bridge.quote(req.symbol)
            if quote.bid <= 0 or quote.ask <= 0 or quote.ask < quote.bid:
                data_problems.append(f"invalid quote for {req.symbol}")
        except Exception as exc:
            logger.warning("Quote unavailable for %s: %s", req.symbol, exc)
            data_problems.append(f"quote unavailable for {req.symbol}")
        try:
            symbol_info = self.bridge.symbol_info(req.symbol)
        except Exception as exc:
            logger.warning("Symbol info unavailable for %s: %s", req.symbol, exc)
            data_problems.append(f"symbol contract data unavailable for {req.symbol}")
        try:
            positions = self.bridge.positions()
            open_positions = len(positions)
        except Exception as exc:
            logger.warning("Positions unavailable: %s", exc)
            positions = []
            open_positions = 0
            data_problems.append("open positions unavailable")
        try:
            closed_trades = self.bridge.closed_trades_today()
        except Exception as exc:
            logger.warning("Closed trades unavailable: %s", exc)
            closed_trades = []
            data_problems.append("today's closed trades unavailable")

        sizing = None
        if quote is not None and symbol_info is not None:
            sizing = calculate_position_sizing(req, quote, symbol_info, account)

        current_portfolio_risk_pct = None
        if account.equity > 0 and "open positions unavailable" not in data_problems:
            risk_amount = 0.0
            info_cache = {req.symbol.upper(): symbol_info}
            portfolio_data_complete = True
            for position in positions:
                if position.sl is None:
                    data_problems.append(
                        f"open position {position.ticket} has no stop loss; portfolio risk is unknown"
                    )
                    portfolio_data_complete = False
                    continue
                key = position.symbol.upper()
                info = info_cache.get(key)
                if info is None:
                    try:
                        info = self.bridge.symbol_info(position.symbol)
                        info_cache[key] = info
                    except Exception as exc:
                        logger.warning(
                            "Symbol info unavailable for open position %s: %s",
                            position.ticket,
                            exc,
                        )
                        data_problems.append(
                            f"symbol contract data unavailable for open position {position.ticket}"
                        )
                        portfolio_data_complete = False
                        continue
                amount = position_risk_amount(position, info)
                if amount is None:
                    portfolio_data_complete = False
                    continue
                risk_amount += amount
            if portfolio_data_complete:
                current_portfolio_risk_pct = (risk_amount / account.equity) * 100.0

        daily_loss_pct = 0.0
        minutes_since_last_loss = None
        if "today's closed trades unavailable" not in data_problems:
            realized_pnl = sum(trade.profit for trade in closed_trades)
            start_balance = account.balance - realized_pnl
            if start_balance <= 0:
                data_problems.append("start-of-day balance cannot be determined")
            else:
                daily_loss_pct = max(0.0, (-realized_pnl / start_balance) * 100.0)
            losing_trades = [trade for trade in closed_trades if trade.profit < 0]
            if losing_trades:
                last_loss_at = max(trade.close_time for trade in losing_trades)
                if last_loss_at.tzinfo is None:
                    last_loss_at = last_loss_at.replace(tzinfo=timezone.utc)
                minutes_since_last_loss = max(
                    0.0,
                    (datetime.now(timezone.utc) - last_loss_at).total_seconds() / 60.0,
                )

        news = self._news_risk(req.symbol)
        volatility = self._volatility_risk(req.symbol)
        if account.account_type is AccountType.REAL:
            if not news.is_live:
                data_problems.append("live economic-calendar/news data unavailable for real account")
            if not volatility.is_live:
                data_problems.append("live volatility/session data unavailable for real account")
        return RiskContext(
            request=req,
            trading_mode=self.settings.trading_mode,
            account=account,
            bridge_health=health,
            quote=quote,
            symbol_info=symbol_info,
            positions=positions,
            closed_trades_today=closed_trades,
            open_positions=open_positions,
            trades_today=self.orders.count_today(),
            daily_loss_pct=daily_loss_pct,
            minutes_since_last_loss=minutes_since_last_loss,
            abnormal_volatility=volatility.abnormal,
            volatility=volatility,
            news=news,
            config_problems=self.settings.validate_safety(),
            data_problems=data_problems,
            estimated_loss=sizing.estimated_loss if sizing else None,
            estimated_reward=sizing.estimated_reward if sizing else None,
            sized_risk_pct=sizing.sized_risk_pct if sizing else None,
            max_volume_for_risk=sizing.max_volume_for_risk if sizing else None,
            current_portfolio_risk_pct=current_portfolio_risk_pct,
        )

    def _news_risk(self, symbol: str) -> NewsRisk:
        if self.news_provider is None:
            return NewsRisk(summary="News provider is not configured")
        try:
            return self.news_provider.news_risk(symbol)
        except Exception as exc:
            logger.warning("News provider unavailable for %s: %s", symbol, exc)
            # If the news source is broken we cannot prove it is safe -> flag risk.
            return NewsRisk(
                has_high_impact_within_window=True,
                summary="News provider unavailable",
            )

    def _volatility_risk(self, symbol: str) -> VolatilityRisk:
        if self.volatility_provider is None:
            return VolatilityRisk(summary="Volatility provider is not configured")
        try:
            return self.volatility_provider.volatility_risk(symbol)
        except Exception as exc:
            logger.warning("Volatility provider unavailable for %s: %s", symbol, exc)
            return VolatilityRisk(
                abnormal=True,
                summary="Volatility provider unavailable",
            )

    def _safe_health(self) -> BridgeHealth:
        try:
            status = self.bridge.health()
        except Exception:
            logger.warning("Bridge health check failed; treating as UNKNOWN")
            return BridgeHealth.UNKNOWN
        if status.health is not BridgeHealth.HEALTHY:
            return status.health
        if status.last_heartbeat is None:
            logger.warning("Bridge reports healthy without a heartbeat timestamp")
            return BridgeHealth.UNKNOWN
        heartbeat = status.last_heartbeat
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - heartbeat).total_seconds()
        max_age = getattr(
            self.bridge,
            "heartbeat_max_age_sec",
            self.settings.mt5_heartbeat_max_age_sec,
        )
        if age > max_age or age < -max_age:
            logger.warning("Bridge heartbeat is stale or clock-skewed (age=%.1fs)", age)
            return BridgeHealth.UNKNOWN
        return BridgeHealth.HEALTHY

    def _safe_account(self) -> AccountInfo:
        try:
            return self.bridge.account_info()
        except Exception:
            logger.warning("Account info unavailable; treating account type as UNKNOWN")
            return AccountInfo(account_type=AccountType.UNKNOWN)

    # ── Result builders ──────────────────────────────────────────────────────
    def _mark_reconciliation_required(
        self,
        row: OrderRow,
        risk: RiskResult,
        message: str,
        *,
        mt5_response: dict | None = None,
    ) -> OrderResult:
        current = OrderState(row.state)
        if current is not OrderState.RECONCILIATION_REQUIRED:
            state_machine.assert_transition(current, OrderState.RECONCILIATION_REQUIRED)
            self.orders.update_state(
                row,
                state=OrderState.RECONCILIATION_REQUIRED.value,
                message=message,
            )
        self.audit.write(
            event="order.reconciliation_required",
            idempotency_key=row.idempotency_key,
            order_id=row.id,
            symbol=row.symbol,
            account_type=row.account_type,
            trading_mode=row.trading_mode,
            decision=risk.decision.value,
            strategy_reason=row.strategy_reason,
            ai_reason=row.ai_reason,
            mt5_response=mt5_response,
            payload={"reason": message},
        )
        return self._result(
            row,
            risk,
            OrderState.RECONCILIATION_REQUIRED,
            mt5_response=mt5_response,
            message=message,
        )

    def _claim_transition(
        self,
        row: OrderRow,
        src: OrderState,
        dst: OrderState,
        risk: RiskResult,
        *,
        event: str,
        message: str,
        user_approval: bool | None = None,
    ) -> OrderResult:
        state_machine.assert_transition(src, dst)
        if not self.orders.claim_state(row.id, expected=src.value, new=dst.value):
            self.session.refresh(row)
            return self._result_from_row(
                row, message=f"Order was already handled (state={row.state})"
            )
        self.session.refresh(row)
        self.orders.update_state(row, state=dst.value, message=message)
        self.audit.write(
            event=event, idempotency_key=row.idempotency_key, order_id=row.id, symbol=row.symbol,
            account_type=row.account_type, trading_mode=row.trading_mode, decision=risk.decision.value,
            strategy_reason=row.strategy_reason, ai_reason=row.ai_reason,
            user_approval=user_approval,
            payload={"reasons": risk.reasons, "warnings": risk.warnings},
        )
        return self._result(row, risk, dst, message=message)

    def _mark_execution_error(
        self,
        row: OrderRow,
        risk: RiskResult,
        message: str,
        *,
        mt5_response: dict | None = None,
    ) -> OrderResult:
        state_machine.assert_transition(OrderState.SUBMITTED, OrderState.ERROR)
        self.orders.update_state(row, state=OrderState.ERROR.value, message=message)
        self.audit.write(
            event="order.error", idempotency_key=row.idempotency_key, order_id=row.id,
            symbol=row.symbol, account_type=row.account_type, trading_mode=row.trading_mode,
            decision=risk.decision.value, strategy_reason=row.strategy_reason,
            ai_reason=row.ai_reason, mt5_response=mt5_response, payload={"error": message},
        )
        return self._result(
            row, risk, OrderState.ERROR, mt5_response=mt5_response, message=message
        )

    def _transition(self, row: OrderRow, src: OrderState, dst: OrderState, risk: RiskResult,
                    *, event: str, message: str, user_approval: bool | None = None) -> OrderResult:
        state_machine.assert_transition(src, dst)
        self.orders.update_state(row, state=dst.value, message=message)
        self.audit.write(
            event=event, idempotency_key=row.idempotency_key, order_id=row.id, symbol=row.symbol,
            account_type=row.account_type, trading_mode=row.trading_mode, decision=risk.decision.value,
            strategy_reason=row.strategy_reason, ai_reason=row.ai_reason, user_approval=user_approval,
            payload={"reasons": risk.reasons, "warnings": risk.warnings},
        )
        return self._result(row, risk, dst, message=message)

    def _block_without_context(self, req: OrderRequest, *, reason: str) -> OrderResult:
        """Block before any order row exists (e.g. suspected duplicate)."""
        risk = RiskResult(decision=RiskDecision.BLOCK, reasons=[reason])
        self.risk_repo.record(req.symbol, risk, req.idempotency_key)
        self.audit.write(
            event="order.blocked", idempotency_key=req.idempotency_key, symbol=req.symbol,
            trading_mode=self.settings.trading_mode.value, decision=RiskDecision.BLOCK.value,
            strategy_reason=req.strategy_reason, ai_reason=req.ai_reason,
            payload={"reasons": [reason]},
        )
        return OrderResult(
            idempotency_key=req.idempotency_key, state=OrderState.RISK_BLOCKED,
            decision=RiskDecision.BLOCK, reasons=[reason],
            trading_mode=self.settings.trading_mode, message=reason,
        )

    def _result(self, row: OrderRow, risk: RiskResult, state: OrderState, *,
                mt5_response: dict | None = None, message: str = "") -> OrderResult:
        return OrderResult(
            idempotency_key=row.idempotency_key,
            state=state,
            decision=risk.decision,
            reasons=list(risk.reasons),
            warnings=list(risk.warnings),
            order_id=row.id,
            mt5_response=mt5_response,
            account_type=AccountType(row.account_type),
            trading_mode=TradingMode(row.trading_mode),
            created_at=row.created_at,
            message=message,
        )

    def _result_from_row(self, row: OrderRow, *, message: str = "") -> OrderResult:
        return OrderResult(
            idempotency_key=row.idempotency_key,
            state=OrderState(row.state),
            decision=RiskDecision(row.decision),
            order_id=row.id,
            account_type=AccountType(row.account_type),
            trading_mode=TradingMode(row.trading_mode),
            created_at=row.created_at,
            message=message,
        )

    def _request_from_row(self, row: OrderRow) -> OrderRequest:
        return OrderRequest(
            symbol=row.symbol,
            side=OrderSide(row.side),
            volume=row.volume,
            sl=row.sl,
            tp=row.tp,
            risk_pct=row.risk_pct,
            idempotency_key=row.idempotency_key,
            source=row.source,
            strategy_reason=row.strategy_reason,
            ai_reason=row.ai_reason,
            requested_by=row.requested_by,
        )
