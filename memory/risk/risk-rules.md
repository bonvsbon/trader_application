# Risk Rules (reference)

> The authoritative risk parameters live in `.env` / `app/core/config.py` and are
> enforced by `app/risk/`. This file is human reference only. **The AI must not
> change risk rules here or in config without explicit user approval.**

Active guards (see `app/risk/rules.py`): config-present, required-risk-data,
emergency-stop, account-type-known, bridge-health/heartbeat, high-impact-news,
spread, volatility, margin/equity, daily-loss, max-trades, max-positions,
max-order-volume, risk-per-trade, portfolio-risk, cooldown, real-account-guard,
and automation-mode/reason guards.
