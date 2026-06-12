# 01 · Navigation & Global Shell

Source: `frontend/src/App.vue`, `frontend/src/router/index.ts`, `frontend/src/style.css`

## App shell layout

```
┌──────────────┬──────────────────────────────────────────────┐
│  SIDEBAR     │  TOPBAR  (sticky, blur)                        │
│  (244px,     │  ├ Safety strip: Account · Mode · Bridge ·     │
│   sticky)    │  │   [Emergency stop] [Auto-real live]         │
│              │  └ Theme toggle (light/dark)                   │
│  ◇ ทางรอด    ├──────────────────────────────────────────────┤
│              │                                                │
│  [nav        │  CONTENT  (max-width 1120px, centered)         │
│   groups]    │  └ <router-view/>                              │
│              │                                                │
│  ┌────────┐  │                                                │
│  │Workflow│  │                                                │
│  │countdown  │                                                │
│  └────────┘  │                                                │
└──────────────┴──────────────────────────────────────────────┘
```

- **Sidebar** background `--surface-2`, right border; sticky full-height.
  Bottom holds the **IntervalCountdown** widget (see 03_components).
- **Topbar** sticky, translucent (`backdrop-filter: blur(8px)`), bottom border.
- **Content** padding `--sp-9 --sp-8 --sp-12`, centered, max 1120px.
- Backend offline → safety strip shows a single `UNKNOWN` "Backend offline" badge.

## Sidebar navigation (3 labeled groups, 11 routes)

Brand mark: `◇ ทางรอด` (accent square + Thai wordmark).

### Group: TRADING
| Label | Route | Icon (lucide-style stroke) |
|---|---|---|
| Dashboard | `/dashboard` | grid / bento |
| Manual Order | `/order` | plus-in-square |
| Strategy | `/strategy` | trend-up + flag |
| Approvals | `/approvals` | check-in-square |

### Group: MONITORING
| Label | Route | Icon |
|---|---|---|
| Risk Monitor | `/risk` | shield-check |
| History | `/history` | clock-rewind |
| AI Analysis | `/analysis` | atom / orbit |
| Logs | `/logs` | list-lines |

### Group: SETTINGS (pinned bottom, divider above)
| Label | Route | Icon |
|---|---|---|
| MT5 Account | `/account` | stacked-bars |
| Providers | `/settings/providers` | cog |
| Market Data | `/settings/market-data` | line-chart |

- `/` → redirect `/dashboard`.
- Active link: accent-tinted background + accent text + weight 600.
- Group section labels: tiny uppercase, `--ink-faint`.
- `.nav-scroll` wraps the two top groups with `overflow-y:auto` so links scroll
  on short viewports while SETTINGS stays pinned at the bottom.

## Topbar safety strip (always visible)

| Item | Source | Render |
|---|---|---|
| Account | `dashboard.account.account_type` | badge: DEMO=green, REAL/UNKNOWN=red |
| Mode | `dashboard.trading_mode` | mono badge (e.g. MANUAL_ONLY) |
| Bridge | `dashboard.bridge_health` | badge HEALTHY/UNHEALTHY/UNKNOWN |
| Emergency stop | `safety_flags.emergency_stop` | red BLOCK badge (only if true) |
| Auto-real live | `safety_flags.auto_real_full_enabled` | red BLOCK badge (only if true) |

Refreshes every 8s via `GET /api/dashboard`.

## Theme toggle
Sun/moon icon button (top-right). Persists via `useTheme` composable; sets
`[data-theme]` on `<html>`. All colors are token-driven (see 04_design_tokens).

## Responsive behavior (≤ 860px)
- Sidebar becomes a **horizontal scrolling bar** across the top.
- Group labels hidden; all links collapse into one scroll row.
- Countdown widget hidden on mobile.
- Touch targets ≥ 44px on coarse pointers; respects `prefers-reduced-motion`.
