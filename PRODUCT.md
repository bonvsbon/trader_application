# Product: ทางรอด

## Register

product

## Users

A solo discretionary/semi-automated trader running a MetaTrader 5 account (starting with XAUUSD/Gold). They sit in front of the app while the market is live, often under time pressure, deciding whether to place a trade, approve an automated proposal, or stand aside. They care about not losing money to avoidable mistakes far more than about squeezing every opportunity.

## Product Purpose

A safety-first trading cockpit that integrates with MT5 for manual and (later) automated trading. It exists to make the *safe* action the obvious one: every order passes a Risk Manager, real-money orders require explicit confirmation, and the system blocks trading whenever it is unsure (unknown account/bridge, missing config, high-impact news). Success = the user trusts what the screen tells them and never places an order they didn't intend.

## Brand Personality

Calm, trustworthy, precise. The voice of a senior risk desk: quiet confidence, plain language, no hype. Three words: **composed, transparent, exact.** The interface should lower the user's heart rate, not raise it.

## Anti-references

- **Crypto / casino hype**: neon gradients, glowing buttons, confetti, "🚀 to the moon" energy, flashing tickers. Money is serious; the UI must not gamify it.
- **Generic Bootstrap admin**: stock card grids, default blue, undifferentiated tables. Familiar is good; characterless is not.
- **Bloomberg-terminal overload**: walls of data with no hierarchy. Density is earned per panel, not dumped on every screen.

## Design Principles

1. **Safety is legible.** The current trading mode, bridge health, and whether trading is blocked are always visible and unambiguous. The user never has to guess if it's safe.
2. **Calm under pressure.** Low visual noise, generous breathing room, restrained color. Nothing moves or flashes unless it conveys a real state change.
3. **Numbers are first-class.** Prices, P&L, lots, R-multiples are monospaced, tabular, and aligned so they're scannable at a glance and never shift.
4. **Trust through transparency.** Every risk decision shows its reasons; every order shows its state and audit trail. The system explains itself.
5. **Familiar, not clever.** Standard affordances for standard tasks (forms, tables, modals). Invention is reserved for the one thing that matters: the safety/decision surface.

## Accessibility & Inclusion

- Target **WCAG 2.1 AA**: body text ≥4.5:1, large text/UI ≥3:1, in both light and dark themes.
- Full keyboard operability with a visible `:focus-visible` ring on every interactive element.
- Honor `prefers-reduced-motion`: countdown and transitions degrade to instant/crossfade.
- Decision and P&L state is never carried by color alone — always paired with a text label or icon (ALLOW/WARN/BLOCK, +/−).
