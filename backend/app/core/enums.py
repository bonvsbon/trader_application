"""Shared enumerations used across the trading domain.

Kept in `core` (not `domain`) so both the domain layer and the framework edges
can import them without creating a dependency cycle.
"""

from __future__ import annotations

from enum import Enum


class TradingMode(str, Enum):
    """How the system is allowed to place orders.

    Ordering matters for safety: anything beyond MANUAL_ONLY widens automation,
    and AUTO_REAL_FULL is the only mode that may place real orders without a
    per-order human approval — and only when multiple config flags agree.
    """

    MANUAL_ONLY = "MANUAL_ONLY"
    AUTO_DEMO = "AUTO_DEMO"
    AUTO_REAL_APPROVAL_REQUIRED = "AUTO_REAL_APPROVAL_REQUIRED"
    AUTO_REAL_FULL = "AUTO_REAL_FULL"


class AccountType(str, Enum):
    """Resolved account type. UNKNOWN must always block trading."""

    DEMO = "DEMO"
    REAL = "REAL"
    UNKNOWN = "UNKNOWN"


class RiskDecision(str, Enum):
    """The Risk Engine verdict. Only ALLOW permits execution."""

    ALLOW = "ALLOW"
    WARN = "WARN"
    BLOCK = "BLOCK"


class BridgeHealth(str, Enum):
    """MT5 bridge connectivity state. Anything other than HEALTHY blocks trading."""

    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderState(str, Enum):
    """Lifecycle of an order request as it moves through the chokepoint.

    Terminal states: FILLED, REJECTED, CANCELLED, ERROR, RISK_BLOCKED.
    PENDING_APPROVAL is a holding state for real-account orders awaiting a human.
    """

    PENDING = "PENDING"                  # created, not yet evaluated
    RISK_BLOCKED = "RISK_BLOCKED"        # Risk Engine returned BLOCK (terminal)
    PENDING_APPROVAL = "PENDING_APPROVAL"  # real account, awaiting manual confirmation
    APPROVED = "APPROVED"                # human approved, ready to submit
    SUBMITTED = "SUBMITTED"              # sent to bridge, awaiting result
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"  # outcome uncertain; query MT5
    FILLED = "FILLED"                    # executed by MT5 (terminal)
    REJECTED = "REJECTED"                # bridge/broker rejected (terminal)
    CANCELLED = "CANCELLED"              # cancelled before submit (terminal)
    ERROR = "ERROR"                      # unexpected failure (terminal)
