"""Order state machine.

Documents and enforces legal transitions. Terminal states have no outgoing
edges. The chokepoint asserts each transition so an illegal move (e.g. executing
an already-blocked order) raises instead of silently proceeding.
"""

from __future__ import annotations

from app.core.enums import OrderState
from app.domain.errors import ExecutionError

_ALLOWED: dict[OrderState, set[OrderState]] = {
    OrderState.PENDING: {
        OrderState.RISK_BLOCKED,
        OrderState.PENDING_APPROVAL,
        OrderState.APPROVED,
        OrderState.SUBMITTED,
        OrderState.CANCELLED,
        OrderState.ERROR,
    },
    OrderState.PENDING_APPROVAL: {
        OrderState.APPROVED,
        OrderState.SUBMITTED,
        OrderState.CANCELLED,
        OrderState.RISK_BLOCKED,  # re-evaluation at approval time may now block
        OrderState.ERROR,
    },
    OrderState.APPROVED: {OrderState.SUBMITTED, OrderState.CANCELLED, OrderState.ERROR},
    OrderState.SUBMITTED: {
        OrderState.FILLED,
        OrderState.REJECTED,
        OrderState.RECONCILIATION_REQUIRED,
        OrderState.ERROR,
    },
    OrderState.RECONCILIATION_REQUIRED: {
        OrderState.SUBMITTED,
        OrderState.FILLED,
        OrderState.REJECTED,
        OrderState.ERROR,
    },
    # Terminal states:
    OrderState.RISK_BLOCKED: set(),
    OrderState.FILLED: set(),
    OrderState.REJECTED: set(),
    OrderState.CANCELLED: set(),
    OrderState.ERROR: set(),
}


def can_transition(src: OrderState, dst: OrderState) -> bool:
    return dst in _ALLOWED.get(src, set())


def assert_transition(src: OrderState, dst: OrderState) -> None:
    if not can_transition(src, dst):
        raise ExecutionError(f"Illegal order transition {src.value} -> {dst.value}")
