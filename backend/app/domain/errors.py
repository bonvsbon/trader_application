"""Domain exceptions.

Execution code prefers returning a structured BLOCK result over raising, so the
caller always gets reasons. These exceptions cover genuinely exceptional paths
(misconfiguration, bridge transport failure) that the chokepoint converts into a
safe BLOCK/ERROR result with reasons.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for domain-level errors."""


class ConfigError(DomainError):
    """Configuration is missing or invalid."""


class BridgeError(DomainError):
    """Generic MT5 bridge failure."""


class BridgeUnavailableError(BridgeError):
    """The MT5 bridge is unreachable or unhealthy."""


class ExecutionError(DomainError):
    """An order could not be executed for an unexpected reason."""
