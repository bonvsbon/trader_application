"""Risk Engine — the authoritative ALLOW/WARN/BLOCK decision.

The engine runs every rule and aggregates findings:
  - any BLOCK finding  -> decision BLOCK (with all block reasons)
  - else any WARN      -> decision WARN  (with warnings)
  - else               -> decision ALLOW

Only ALLOW permits automatic execution. The order chokepoint decides how to
treat WARN (manual confirmation) — the engine itself just reports.
"""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.enums import RiskDecision
from app.domain.models import RiskContext, RiskResult
from app.risk import rules
from app.risk.rules import Rule

ALL_RULES: list[Rule] = [
    rules.rule_config_present,
    rules.rule_required_data_present,
    rules.rule_emergency_stop,
    rules.rule_account_type_known,
    rules.rule_bridge_health,
    rules.rule_high_impact_news,
    rules.rule_spread,
    rules.rule_volatility,
    rules.rule_margin,
    rules.rule_daily_loss,
    rules.rule_max_trades,
    rules.rule_max_positions,
    rules.rule_order_prices,
    rules.rule_order_volume,
    rules.rule_position_sizing,
    rules.rule_risk_per_trade,
    rules.rule_portfolio_risk,
    rules.rule_cooldown,
    rules.rule_real_account_guard,
    rules.rule_automation_guard,
]


class RiskEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def evaluate(self, ctx: RiskContext) -> RiskResult:
        block_reasons: list[str] = []
        warnings: list[str] = []
        for rule in ALL_RULES:
            for finding in rule(ctx, self.settings):
                if finding.level is RiskDecision.BLOCK:
                    block_reasons.append(finding.reason)
                elif finding.level is RiskDecision.WARN:
                    warnings.append(finding.reason)

        if block_reasons:
            return RiskResult(decision=RiskDecision.BLOCK, reasons=block_reasons, warnings=warnings)
        if warnings:
            return RiskResult(decision=RiskDecision.WARN, reasons=[], warnings=warnings)
        return RiskResult(decision=RiskDecision.ALLOW, reasons=["All risk checks passed"], warnings=[])
