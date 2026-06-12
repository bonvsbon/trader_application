"""Individual risk rules.

Each rule is a pure function of (RiskContext, Settings) returning a list of
Findings. A rule never executes anything; it only reports. The engine aggregates
findings into a single ALLOW/WARN/BLOCK decision.

Adding a rule = write a function and append it to `ALL_RULES` in engine.py.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.core.config import Settings
from app.core.enums import AccountType, BridgeHealth, RiskDecision, TradingMode
from app.domain.models import RiskContext
from app.risk.sizing import entry_price, price_directions_valid, volume_aligned


@dataclass(frozen=True)
class Finding:
    level: RiskDecision  # BLOCK or WARN
    reason: str


Rule = Callable[[RiskContext, Settings], list[Finding]]


def rule_config_present(ctx: RiskContext, s: Settings) -> list[Finding]:
    # Missing/invalid config must block (safety rule M.10).
    return [Finding(RiskDecision.BLOCK, f"Config invalid: {p}") for p in ctx.config_problems]


def rule_required_data_present(ctx: RiskContext, s: Settings) -> list[Finding]:
    return [Finding(RiskDecision.BLOCK, f"Risk data unavailable: {p}") for p in ctx.data_problems]


def rule_emergency_stop(ctx: RiskContext, s: Settings) -> list[Finding]:
    if s.emergency_stop:
        return [Finding(RiskDecision.BLOCK, "Emergency stop (kill switch) is active")]
    return []


def rule_account_type_known(ctx: RiskContext, s: Settings) -> list[Finding]:
    if ctx.account.account_type is AccountType.UNKNOWN:
        return [Finding(RiskDecision.BLOCK, "Account type is unknown")]
    return []


def rule_bridge_health(ctx: RiskContext, s: Settings) -> list[Finding]:
    if ctx.bridge_health is not BridgeHealth.HEALTHY:
        return [Finding(RiskDecision.BLOCK, f"MT5 bridge is not healthy ({ctx.bridge_health.value})")]
    return []


def rule_high_impact_news(ctx: RiskContext, s: Settings) -> list[Finding]:
    if ctx.news.has_high_impact_within_window:
        mins = ctx.news.minutes_to_next_high_impact
        when = f" within {mins:.0f} min" if mins is not None else ""
        return [Finding(RiskDecision.BLOCK, f"High-impact news{when}: {ctx.news.summary or 'event nearby'}")]
    return []


def rule_spread(ctx: RiskContext, s: Settings) -> list[Finding]:
    if ctx.quote and ctx.quote.spread_points > s.risk_max_spread_points:
        return [Finding(
            RiskDecision.BLOCK,
            f"Spread {ctx.quote.spread_points:.0f} > limit {s.risk_max_spread_points:.0f} points",
        )]
    return []


def rule_volatility(ctx: RiskContext, s: Settings) -> list[Finding]:
    if ctx.abnormal_volatility:
        return [Finding(RiskDecision.BLOCK, "Abnormal volatility detected")]
    return []


def rule_margin(ctx: RiskContext, s: Settings) -> list[Finding]:
    acct = ctx.account
    if acct.equity <= 0:
        return [Finding(RiskDecision.BLOCK, "Account equity is unavailable or non-positive")]
    if acct.free_margin_pct < s.risk_min_free_margin_pct:
        return [Finding(
            RiskDecision.BLOCK,
            f"Free margin {acct.free_margin_pct:.0f}% below safe minimum {s.risk_min_free_margin_pct:.0f}%",
        )]
    return []


def rule_daily_loss(ctx: RiskContext, s: Settings) -> list[Finding]:
    if ctx.daily_loss_pct >= s.risk_daily_max_loss_pct:
        return [Finding(
            RiskDecision.BLOCK,
            f"Daily loss {ctx.daily_loss_pct:.1f}% reached limit {s.risk_daily_max_loss_pct:.1f}%",
        )]
    return []


def rule_max_trades(ctx: RiskContext, s: Settings) -> list[Finding]:
    if ctx.trades_today >= s.risk_max_trades_per_day:
        return [Finding(
            RiskDecision.BLOCK,
            f"Max trades/day reached ({ctx.trades_today}/{s.risk_max_trades_per_day})",
        )]
    return []


def rule_max_positions(ctx: RiskContext, s: Settings) -> list[Finding]:
    if ctx.open_positions >= s.risk_max_open_positions:
        return [Finding(
            RiskDecision.BLOCK,
            f"Max open positions reached ({ctx.open_positions}/{s.risk_max_open_positions})",
        )]
    return []


def rule_order_prices(ctx: RiskContext, s: Settings) -> list[Finding]:
    if ctx.request.source == "probe":
        return []
    if ctx.quote is None:
        return []
    entry = entry_price(ctx.request, ctx.quote)
    return [
        Finding(RiskDecision.BLOCK, problem)
        for problem in price_directions_valid(ctx.request, entry)
    ]


def rule_order_volume(ctx: RiskContext, s: Settings) -> list[Finding]:
    findings: list[Finding] = []
    volume = ctx.request.volume
    if volume > s.risk_max_order_volume_lots:
        findings.append(Finding(
            RiskDecision.BLOCK,
            f"Order volume {volume:g} lots exceeds safety limit "
            f"{s.risk_max_order_volume_lots:g} lots",
        ))
    info = ctx.symbol_info
    if info is not None:
        if volume < info.volume_min or volume > info.volume_max:
            findings.append(Finding(
                RiskDecision.BLOCK,
                f"Order volume {volume:g} is outside broker range "
                f"{info.volume_min:g}-{info.volume_max:g} lots",
            ))
        if not volume_aligned(volume, info.volume_step):
            findings.append(Finding(
                RiskDecision.BLOCK,
                f"Order volume {volume:g} does not match broker step {info.volume_step:g}",
            ))
    return findings


def rule_position_sizing(ctx: RiskContext, s: Settings) -> list[Finding]:
    if ctx.request.source == "probe":
        return []
    if ctx.max_volume_for_risk is None:
        return []
    if ctx.max_volume_for_risk <= 0:
        return [Finding(
            RiskDecision.BLOCK,
            "Configured risk is too small for the broker minimum volume at this stop distance",
        )]
    if ctx.request.volume > ctx.max_volume_for_risk + 1e-9:
        return [Finding(
            RiskDecision.BLOCK,
            f"Order volume {ctx.request.volume:g} exceeds risk-sized maximum "
            f"{ctx.max_volume_for_risk:g} lots",
        )]
    return []


def rule_risk_per_trade(ctx: RiskContext, s: Settings) -> list[Finding]:
    rp = ctx.request.risk_pct
    if rp is None:
        return [Finding(RiskDecision.BLOCK, "Risk percentage is required")]
    if rp > s.risk_max_risk_per_trade_pct:
        return [Finding(
            RiskDecision.BLOCK,
            f"Requested risk {rp:.2f}% exceeds max per trade {s.risk_max_risk_per_trade_pct:.2f}%",
        )]
    return []


def rule_portfolio_risk(ctx: RiskContext, s: Settings) -> list[Finding]:
    if ctx.current_portfolio_risk_pct is None or ctx.sized_risk_pct is None:
        return []
    projected = ctx.current_portfolio_risk_pct + ctx.sized_risk_pct
    if projected > s.risk_max_portfolio_risk_pct:
        return [Finding(
            RiskDecision.BLOCK,
            f"Projected portfolio risk {projected:.1f}% exceeds max {s.risk_max_portfolio_risk_pct:.1f}%",
        )]
    return []


def rule_cooldown(ctx: RiskContext, s: Settings) -> list[Finding]:
    m = ctx.minutes_since_last_loss
    if m is not None and m < s.risk_cooldown_minutes_after_loss:
        return [Finding(
            RiskDecision.BLOCK,
            f"Cooldown after loss: {m:.0f} min elapsed, need {s.risk_cooldown_minutes_after_loss} min",
        )]
    return []


def rule_real_account_guard(ctx: RiskContext, s: Settings) -> list[Finding]:
    if ctx.account.account_type is AccountType.REAL and not s.allow_real_trading:
        return [Finding(RiskDecision.BLOCK, "Real-account trading is disabled (ALLOW_REAL_TRADING=false)")]
    return []


def rule_automation_guard(ctx: RiskContext, s: Settings) -> list[Finding]:
    if ctx.request.source != "auto":
        return []
    findings: list[Finding] = []
    if ctx.trading_mode is TradingMode.MANUAL_ONLY:
        findings.append(Finding(RiskDecision.BLOCK, "Automated orders are disabled in MANUAL_ONLY mode"))
    if not ctx.request.strategy_reason:
        findings.append(Finding(RiskDecision.BLOCK, "Automated order requires a strategy reason"))
    if not ctx.request.ai_reason:
        findings.append(Finding(RiskDecision.BLOCK, "Automated order requires an AI reason"))
    return findings
