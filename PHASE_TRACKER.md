# ทางรอด Phase Tracker

Last updated: 2026-06-12

Status legend:

- `[x] Done` - implemented and currently verified
- `[~] Partial` - foundation exists, but required behavior is incomplete
- `[ ] Not started` - no functional implementation yet

## Current Status

The project has a functional **Phase 1 safety foundation** and has started the
Phase 2 strategy/proposal layer. The mock/demo flow is functional.
Live MT5 and real-money use are not production-ready.

Latest verification:

- Backend: `136 passed`
- Backend lint: Ruff passed
- Frontend: TypeScript check and production build passed
- Database: Alembic revision `0011_identity_foundation` is at head
- PostgreSQL: local PostgreSQL 16 database created and migrations verified
- Runtime: backend/frontend online; API and market/workflow WebSockets verified

### Live-MT5 Release Gate

- `[x]` All order execution routes through `OrderService`
- `[x]` Unknown account or unhealthy/stale bridge blocks trading
- `[x]` Missing quote or open-position data blocks trading
- `[x]` Broker responses are classified instead of assumed filled
- `[x]` Configurable hard ceiling for order volume
- `[x]` Real trading and auto-real are disabled by default
- `[x]` Position sizing from equity, SL distance, and symbol contract data
- `[~]` Real daily-loss, cooldown, volatility, and portfolio-risk inputs
  Daily loss, cooldown, and SL-based portfolio risk are wired. Live news and
  volatility adapters are not; mock providers are explicitly unavailable and
  block real-account execution.
- `[x]` Fail-closed live news and volatility gates for real-money trading
  Real trading rejects mock/missing provider data; the UI reports unavailable
  feeds instead of presenting them as clear.
- `[x]` Atomic idempotency and approval claims at the database layer
- `[~]` Reconciliation after timeout, disconnect, or uncertain broker result
  Backend state, API, workflow polling, expiry alerts, and EA implementation
  exist; MetaEditor compilation and demo-account verification remain.
- `[~]` Authentication and authorization for sensitive APIs
  Browser sessions now use each owner's MT5 login number as the username, with
  a separate hashed app password, CSRF protection, lockout, and MT5 config
  ownership. Multiple users remain blocked until all trading data is account-scoped.
- `[x]` Authenticate the EA socket connection and enforce a production bind policy
  A required environment-managed shared secret authenticates the EA handshake.
  Remote binds require an explicit opt-in and a protected network/tunnel.
- `[ ]` Live MQL5 EA integration tested on a demo account

## Phase 1 - Foundation, Manual Trading, Demo Safety

Goal: establish the application architecture, manual order flow, mock MT5
integration, and safety-first execution foundation.

- `[x]` Inspect and document project structure
- `[x]` Define ports-and-adapters architecture
- `[x]` Environment-driven configuration
- `[x]` Editable persisted MT5 bridge/account allowlist configuration
  UI/API can replace the bridge at runtime. Passwords are rejected and remain
  inside MT5 Terminal; account login/server/type mismatches block trading.
- `[x]` MT5 bridge abstraction
- `[x]` Mock MT5 bridge
- `[~]` Risk Manager
  Position sizing, daily loss, cooldown, and portfolio risk are calculated from
  bridge data. Live news and volatility inputs remain.
- `[x]` Single order execution chokepoint
- `[x]` Idempotency key and duplicate-order checks
- `[x]` Order state machine
- `[x]` Persistent audit and risk-decision logs
- `[x]` Manual Order page
- `[x]` Real-account confirmation modal
- `[x]` Real-account backend approval gate
- `[x]` Dashboard
- `[x]` MT5 Account Status page
- `[x]` Risk Monitor page
- `[x]` Logs page
- `[x]` Interval Countdown component
- `[x]` Read-only workflow runner
- `[x]` Start/stop/manual-run scheduler
- `[x]` Auto-real disabled by default with multiple safety flags
- `[~]` Backend test coverage
  Core paths are covered; API, concurrency, transaction-failure, and recovery
  tests remain.
- `[~]` Frontend test coverage
  Type-check and production build pass; component and end-to-end tests remain.

## Phase 2 - AI Analysis, News, Strategy Engine

Goal: add advisory AI analysis, real news/volatility data, the first XAUUSD
strategy preset, and trade proposals.

- `[x]` AI provider port and disabled/null provider
- `[x]` Settings menu and Analysis Providers page
  Provider list/detail editor is separate from MT5 execution settings and shows
  health, latency, discovery results, secret-reference state, and active routes.
- `[x]` Persisted AI/MCP provider registry
  Store enabled state, endpoint, transport, timeout, priority, capability
  assignments, health metadata, and secret references. Never store plaintext secrets.
- `[x]` MCP client adapter
  Official MCP Python SDK supports Streamable HTTP plus legacy SSE. Endpoints
  require an exact host allowlist; non-local endpoints require HTTPS. Arbitrary
  UI-defined local commands/stdio servers are not supported.
- `[x]` MCP connection test and tool discovery
  Tests initialize the session, list tools, record latency/health/error, and
  keep tool use deny-by-default behind an explicit allowlist.
- `[x]` Capability routing and per-capability fallback order
  `AnalysisService` resolves enabled healthy providers for all six capabilities,
  calls them by priority, and fails over after a runtime failure.
- `[x]` Provider audit and analysis provenance
  Provider config events are audited without secret values. Every runtime
  attempt records correlation ID, provider/model/tool, latency, result/error,
  and a redacted input summary.
- `[x]` OpenAI provider implementation
  Config-driven Responses API adapter supports model lookup health checks,
  advisory analysis, optional hosted web search, response-size limits,
  `store=false`, exact-host/HTTPS policy, environment secret references, and
  normal capability failover. Live account validation still requires the
  operator's API key and model access.
- `[ ]` Claude provider implementation
- `[x]` Local LLM through Open WebUI
  Settings now persist endpoint, model, enabled state, web-search toggle, and
  explicit Open WebUI tool IDs. Connection tests call `/api/models`, verify the
  configured model, and record health/latency/model discovery. Runtime analysis
  calls `/api/chat/completions` with size limits and integrates with proposal
  explanations, loss reviews, the AI Analysis page, and optional workflow analysis.
- `[x]` Provider failover and health policy
  Runtime requests follow the healthy priority chain and persist each attempt.
  Enabled providers are rechecked automatically on a config-driven interval
  while the workflow scheduler runs. Checks are stale-aware, batch-limited,
  fail-isolated, and can also be triggered for all enabled providers from Settings.
- `[x]` News provider port and mock provider
- `[ ]` Real economic-calendar/news provider
- `[~]` News risk model
  Domain model and BLOCK path exist; score and live event data do not.
- `[ ]` Volatility and market-session provider
- `[x]` XAUUSD AI Analysis page
  Operators can run any supported capability, inspect the result, and review
  recent provider/tool provenance. This page is advisory-only.
- `[x]` Strategy port and null strategy
- `[x]` XAUUSD D40/D20, TP 2R, risk 1% preset
  D40/D20 is now defined as a **Donchian channel breakout**: enter on the latest
  closed bar breaking the 40-bar high/low, SL at the 20-bar channel, TP at the
  reward:risk ratio. `strategy/signal.py` evaluates it from bridge candles and,
  on a breakout, produces a proposal via `ProposalService` (never the broker).
  Automatic evaluation stays gated behind `signal_definition_confirmed`;
  `POST /api/strategy/evaluate-signal` + a Strategy-page button drive it. An
  idealized backtester (`strategy/backtest.py`, `POST /api/strategy/backtest`,
  Strategy-page "Signal backtest" panel) walks the rule over recent candles and
  reports trades/win-rate/total-R/avg-R/max-drawdown in R — a rule-consistency
  sanity check, explicitly not a profitability forecast. Needs live-candle/demo
  validation before real-money use.
- `[x]` Strategy news requirement
  `require_news_clear` is persisted, editable, and blocks proposal submission
  when live provider clearance is unavailable.
- `[x]` Position sizing and risk/reward calculation
- `[x]` Trade proposal persistence and generation
  Persisted drafts include entry/SL/TP/volume, strategy reason, risk snapshot,
  expiry, and idempotent submission through `OrderService`.
- `[x]` AI explanation and analysis snapshot
  Proposals request an advisory explanation through `AnalysisService` when one
  is not supplied. Provider failure does not block manual/demo proposal creation.
- `[x]` Approval flow before execution
  Proposal list/submission and the generic order approval queue exist. The
  pending-approval API now enriches each order with the recorded risk decision
  reasons/warnings and—when it originated from a proposal—the linked strategy
  rationale and advisory AI snapshot (summary + confidence). The Approvals page
  renders this as per-order cards so an operator reviews full context before
  approving. AI remains advisory only.

## Phase 3 - Automation, Learning, Production Hardening

Goal: run controlled automated workflows, reconcile MT5 state, learn from trade
history, and prepare the system for reliable deployment.

- `[~]` Full interval workflow
  Read-only MT5 sync exists; analysis, proposal, risk, and execution steps do not.
- `[x]` Start/stop scheduler
- `[x]` Countdown and manual trigger
- `[ ]` Auto-demo execution through `OrderService`
- `[x]` Real-account approval queue
  Queue API/page, approve/reject actions, risk recheck, and expiry policy exist.
- `[x]` Trade history with P&L and R multiple
  Closed trades sync from the bridge into `closed_trades` (deduped by ticket),
  matched to orders by ticket to compute realized R = profit / planned risk at
  entry. `/api/history` + History page show net P&L, total/avg R, win rate.
  Historical backfill exists (`POST /api/history/backfill?days=N` via the new
  `closed_trades_range` bridge method + a "Backfill" button). Journal snapshots
  (entry/exit price, exit reason, open time, plus strategy/AI reason and risk
  decision captured from the matched order) persist and show in an expandable
  row. Live MT5 deal-vs-order ticket matching still awaits EA demo testing.
- `[~]` Order/position/deal reconciliation with MT5
  Order reconciliation contract, API, automatic workflow polling, and EA handler
  exist. Expiry alerts are deduplicated; demo-account verification remains.
- `[x]` Losing-trade review workflow
  Losing closed trades surface as a review queue (`/api/history/review`); the
  operator records a post-trade note (`POST /api/history/review/{ticket}`),
  stored with reviewer + timestamp and shown as a "Loss review" journal panel.
  An optional AI draft uses the `loss_review` capability and remains editable
  before the operator saves it.
- `[~]` Markdown memory system
  Categorized files exist; controlled read/write workflow does not.
- `[~]` Skill files
  Placeholder files exist.
- `[x]` Daily trading summary
  `/api/history/daily` groups closed trades by close day with per-day P&L, R,
  and win rate; shown as a "By day" panel on the History page. Historical
  backfill now populates past days.
- `[~]` Error recovery
  Uncertain execution results enter `RECONCILIATION_REQUIRED` and workflow polling
  checks MT5 without resubmitting. Expiry alerts exist; bridge-level
  retry/backoff and circuit breaker now exist (`ResilientBridge`); demo recovery
  soak testing remains.
- `[~]` Retry, backoff, and circuit breaker
  `ResilientBridge` wraps the ea_socket transport: idempotent reads get bounded
  jittered-backoff retry and a circuit breaker (config-driven). `execute_order`
  is never retried and `health` always passes through. The workflow scheduler
  now treats account/quote/position/history step failures as partial failures,
  persists their details, and triggers capped scheduler backoff. Per-step retry
  policy for full auto execution remains.
- `[x]` Concurrent idempotency reservation and approval state claiming
- `[~]` Authentication, authorization, and trusted actor identity
  First-owner bootstrap, login/logout/session expiry, CSRF, lockout, protected
  APIs/WebSockets, and MT5 identity/config ownership are implemented. Phase B
  still needs `mt5_account_id` on orders, positions, history, proposals,
  strategy/workflow state, and their repository queries before multiple users
  can be enabled safely.
- `[~]` MQL5 EA implementation and demo soak test
  `mql5/ThangRodBridgeEA.mq5` implements the outbound socket client and protocol
  handlers with a per-login persistent idempotency cache. MetaTrader/MetaEditor
  is not installed in this workspace, so compile and demo soak testing remain.
- `[~]` Docker support
  Backend/frontend Dockerfiles, Nginx proxy, PostgreSQL, health checks, and
  Compose configuration exist. Docker CLI is unavailable in this workspace, so
  image build and runtime verification remain.
- `[x]` Deployment and operations documentation
  `OPERATIONS.md` covers startup, MT5 connectivity, backup/restore, upgrade,
  rollback, and safe network exposure.
- `[ ]` Production secret management
- `[ ]` Metrics, alerting, backup, and restore plan
- `[x]` Production readiness checklist
  `PRODUCTION_READINESS.md` records the explicit safety, MT5, security, and
  operations release gates; unchecked gates still block real-money readiness.

## Remaining Product Surface

- `[~]` Watchlist with price, spread, trend, volatility, AI bias, and trade status
  Dashboard streams read-only bid/ask/spread from configured MT5 or Alpaca.
  Market Data settings control provider, IEX/SIP/delayed feed, symbol defaults,
  limits, and environment secret references. External prices never replace MT5
  risk/execution quotes. In dev the mock bridge now streams a bounded simulated
  live tick (display only — the deterministic execution quote is unchanged) and
  the watchlist colours up/down ticks, so realtime behaviour is demonstrable
  without a live feed. Trend, volatility, AI bias, and persistence remain.
- `[ ]` Realtime chart, timeframe selector, candles, indicators, and trade markers
- `[ ]` Symbol search and instrument detail page
- `[ ]` Pending-order sync, order modification, and position/order close flows
- `[ ]` Manual risk override flow with explicit approval and audit log
- `[x]` Full trade journal snapshots: entry/exit context, AI, risk, and exit reason
  Captured on closed trades and shown in the expandable History row. Live exit
  prices/reasons depend on the EA supplying them (demo testing pending).

## Next Work Queue

1. Continue Phase B of `EA_MULTI_USER_AUTH_PLAN.md`: scope every trading table,
   unique key, service, and repository query by `mt5_account_id`, then add IDOR
   tests before allowing creation of a second user.
2. Compile the authenticated EA in MetaEditor and demo-test connectivity/recovery.
3. Connect a routed MCP capability to a real economic-calendar/news source and
   add volatility/session inputs.
4. Live-test Open WebUI/Ollama and Alpaca credentials/feed entitlement on the
   user's target machines.
5. An idealized backtester now exists; next, demo-validate the D40/D20 Donchian
   signal on real candles and add a live candle feed on the EA (`candles` RPC)
   before relying on it.
6. Live-test the OpenAI fallback with the operator's API key/model access;
   add Claude only if a second cloud vendor is still required.
7. Add reconnect/backoff metrics and soak-test the external market-data stream;
   provider health monitoring is implemented but production alert delivery remains.
8. Extend the interval workflow through analysis, proposal, risk, and auto-demo
   execution (auto-demo now unblocked: signal → proposal exists, gate it on
   `signal_definition_confirmed` + a demo account).
9. Verify Docker images/Compose on a Docker host, then add deployment-grade
   user roles, metrics/alerts, secret management, and production controls.

Update this file whenever a deliverable changes status. A checkbox should move to
`Done` only after implementation and verification.
