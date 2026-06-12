# Design

Visual system for ทางรอด. Calm, trustworthy, precise — a risk desk, not a casino. Light and dark are first-class; tokens are defined in `frontend/src/style.css` and switched via `[data-theme]` on `<html>`.

## Theme

Two themes, user-toggleable, defaulting to the OS `prefers-color-scheme`, persisted in `localStorage`. Neither is "the default" — markets are watched in both bright offices and dark rooms. Color is **Restrained** (product floor): tinted slate-blue neutrals + a single confident blue accent; semantic colors only for state.

## Color (OKLCH)

Hue anchor ≈ 255 (calm blue, leaning slate). Chroma kept low on neutrals and ≤0.18 on semantics — no neon.

### Light
| Role | OKLCH | Use |
|---|---|---|
| `--bg` | `0.985 0.004 255` | app background (faint cool tint, not warm cream) |
| `--surface` | `1 0 0` | panels |
| `--surface-2` | `0.972 0.006 255` | sidebar, top bar, table headers |
| `--ink` | `0.27 0.02 260` | primary text (~12:1) |
| `--ink-muted` | `0.49 0.02 260` | secondary text (≥4.6:1 on bg) |
| `--border` | `0.91 0.008 260` | hairlines |
| `--accent` | `0.55 0.15 255` | primary actions, selection |
| `--accent-ink` | `0.46 0.16 255` | accent used as text/links (≥4.5:1) |
| `--success` | `0.55 0.13 150` · `--warn` `0.62 0.12 70` · `--danger` `0.55 0.19 27` | ALLOW / WARN / BLOCK, P&L |

### Dark
Deep desaturated slate (never `#000`).
| Role | OKLCH |
|---|---|
| `--bg` | `0.19 0.018 260` |
| `--surface` | `0.235 0.02 260` |
| `--surface-2` | `0.215 0.02 260` |
| `--ink` | `0.96 0.008 260` |
| `--ink-muted` | `0.74 0.014 260` (≥4.5:1) |
| `--border` | `0.32 0.02 260` |
| `--accent` | `0.70 0.13 255` · `--accent-ink` `0.78 0.12 255` |
| `--success` `0.72 0.14 150` · `--warn` `0.78 0.12 75` · `--danger` `0.70 0.16 27` |

Semantic **badges** use a tint of the hue for bg + a darker/lighter shade of the *same hue* for text (never gray on color).

## Typography

System stack — zero network dependency (this tool may run on an offline trading box); permitted for product UIs.

- **Sans (UI):** `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` — headings, labels, body.
- **Mono (numbers):** `ui-monospace, "Cascadia Code", "SF Mono", Consolas, monospace` with `font-variant-numeric: tabular-nums` for all prices, lots, P&L, tickets, countdown.
- **Scale (fixed rem, ratio ~1.2):** 12 / 13 / **14 (base)** / 16 / 18 / 22 / 28. Headings 600–700 weight, letter-spacing −0.01 to −0.02em. No fluid clamp (product).
- Body line length ≤ 70ch for prose; tables may run denser.

## Components

Every interactive element ships **default / hover / focus-visible / active / disabled**, plus **loading / error** where relevant.

- **Panel:** `--surface`, 1px `--border`, radius 12, subtle shadow. Not a generic card grid — panels are sized to content and grouped by meaning.
- **Badge:** pill, tinted-hue bg + same-hue text; variants for decision (ALLOW/WARN/BLOCK), state (FILLED/PENDING_APPROVAL/RISK_BLOCKED…), health (HEALTHY/UNHEALTHY/UNKNOWN), account (DEMO/REAL). Always carries a text label.
- **Button:** primary (accent), secondary (surface+border), danger (danger). 1px focus-visible ring offset. `:disabled` drops to 45% with no hover.
- **Input/select:** `--surface-2` fill, `--border`, accent focus ring; placeholder at full muted contrast.
- **Table:** sticky `--surface-2` header, hairline row separators (no zebra), numbers right-aligned + mono.
- **kv row:** label (muted) ↔ value (ink/mono), hairline divider.
- **Empty state:** a sentence that teaches the next action, not "nothing here." **Skeleton** blocks for loading, not center spinners.
- **Safety strip:** persistent top-bar element showing trading mode + bridge health + emergency-stop; the legibility of safety.

## Layout

- App shell: fixed sidebar (nav + countdown) + top bar (brand, safety strip, theme toggle) + scrollable main, max content ~1120px.
- Sidebar navigation places **Settings** in a separate lower utility group.
  Settings contains **Analysis Providers** for AI/MCP configuration; it must not
  be mixed into MT5 Account or Strategy screens.
- Analysis Providers uses a provider list plus detail editor. Each provider row
  shows type, assigned capabilities, enabled state, health, latency, last check,
  and a clear **Test connection** action. Secret values are never rendered.
- Responsive is structural: sidebar collapses under ~860px; grids use `repeat(auto-fit, minmax(240px, 1fr))`.
- Spacing scale (px): 2 4 6 8 12 16 20 24 32 40 48. Vary it for rhythm.
- Radii: 6 / 8 / 12 / pill. Z-index scale: dropdown 100 · sticky 200 · backdrop 300 · modal 310 · toast 400 · tooltip 500.

## Motion

- Durations 120 / 180 / 240 ms; ease `cubic-bezier(0.22, 1, 0.36, 1)` (ease-out, no bounce).
- Motion conveys **state only**: hover/press feedback, panel/result reveal (crossfade), countdown tick, theme switch. No page-load choreography.
- `@media (prefers-reduced-motion: reduce)`: transitions collapse to ~1ms / opacity; countdown updates without animation.

## Accessibility

WCAG AA in both themes (contrasts above are tuned for it). Visible focus ring everywhere. State never by color alone (text label + sign always present). Honor reduced-motion.
