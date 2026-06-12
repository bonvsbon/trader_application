# Project Structure — ทางรอด

Safety-first trading web app integrating MetaTrader 5. Manual + auto trading, XAUUSD first.

## Overview

- **Frontend:** Vue 3 + Vite + TypeScript (`vue-router`, `pinia`, `axios`)
- **Backend:** Python 3.14 + FastAPI (`uvicorn`, `pydantic` v2, `pydantic-settings`)
- **Data access:** SQLAlchemy 2 + Alembic — SQLite (dev) / PostgreSQL (prod)
- **MT5 bridge:** backend TCP server ↔ outbound MQL5 EA client — mock remains the default adapter
- **Architecture:** Ports & Adapters (hexagonal). Pure domain, framework only at the edges.

## Request Flow

```text
Vue page → axios (api/client.ts) → FastAPI route → controller-service
         → domain port (Risk / Bridge / Strategy / AI / News)
Orders ALWAYS go: route → execution/order_service.place_order() → RiskEngine → Bridge → audit_log
```

## Folder Structure

```text
trader_application/
├── CLAUDE.md · PROJECT_STRUCTURE.md · requirements.md · rule.md · README.md · .env.example
├── backend/
│   ├── pyproject.toml · alembic.ini · alembic/
│   ├── app/
│   │   ├── main.py                # FastAPI factory, mount routers + WebSocket, CORS
│   │   ├── core/                  # config.py (env Settings), logging.py, enums.py
│   │   ├── domain/                # models.py, ports.py, errors.py  (pure, no framework)
│   │   ├── risk/                  # rules.py, engine.py  → ALLOW/WARN/BLOCK + reasons
│   │   ├── execution/             # order_service.py (CHOKEPOINT), state_machine.py, idempotency.py
│   │   ├── bridge/                # base.py, mock_bridge.py, ea_socket_bridge.py, protocol.md
│   │   ├── strategy/              # preset, signal evaluation, proposal service
│   │   ├── ai/                    # Open WebUI adapter + central AnalysisService
│   │   ├── providers/             # AI/MCP registry, routing, restricted MCP calls
│   │   ├── market_data/           # MT5/Alpaca read-only quote configuration
│   │   ├── news/  volatility/     # ports + fail-closed unavailable adapters
│   │   ├── workflow/              # runner.py, scheduler.py  (interval status/countdown)
│   │   ├── persistence/           # db.py, entities.py, repositories.py
│   │   └── api/                   # HTTP routes + status/market WebSockets
│   └── tests/                     # test_risk_engine.py, test_order_service.py, test_idempotency.py
├── frontend/
│   ├── package.json · vite.config.ts · index.html · tsconfig.json
│   └── src/
│       ├── main.ts · router/ · api/client.ts · stores/
│       ├── pages/                 # trading, history, AI Analysis, provider/market settings
│       └── components/            # countdown, realtime watchlist, shared UI
├── mql5/                          # ThangRodBridgeEA.mq5 + install/limitations
└── memory/                        # strategy/ risk/ news/ user-rules/ system/ skills/ (markdown)
```

## Folder Responsibilities

| Folder | Responsibility |
|--------|----------------|
| `core/` | Env-driven settings, logging, shared enums. No business logic. |
| `domain/` | Pure models + port interfaces (Protocols). No FastAPI/SQLAlchemy imports. |
| `risk/` | Risk Engine — the authoritative ALLOW/WARN/BLOCK decision + reasons. |
| `execution/` | The single order chokepoint: idempotency, state machine, risk gate, audit. |
| `bridge/` | Runtime-reloadable MT5 adapters plus the configured account allowlist guard. |
| `strategy/` | Preset defaults and persisted, risk-checked trade proposal service. |
| `ai/` | Open WebUI adapter and central advisory `AnalysisService` with failover/provenance. |
| `news/` `volatility/` | Provider ports; real live-data adapters remain Phase 2 work. |
| `providers/` | Persisted AI/MCP registry, restricted MCP client, tool mapping, health, and routing. |
| `market_data/` | Read-only MT5/Alpaca watchlist feed; never an execution-price source. |
| `workflow/` | Interval runner + scheduler (start/stop, last/next run, countdown). |
| `persistence/` | SQLAlchemy engine/session, ORM entities, repositories. |
| `api/` | HTTP routes + WebSocket. Thin — orchestrates services, never executes orders directly. |
| `memory/` | Markdown learning/memory files (small, categorized). |

## Key Conventions

- **Order chokepoint:** nothing calls `bridge.execute()` except `execution/order_service.py`.
- **No hardcode:** risk %, lot, account type, trading mode come from `core/config.py` (env).
- **Fail safe:** unknown account/bridge/config or near high-impact news ⇒ `BLOCK`.
- **Audit always:** every order writes an `audit_log` row (strategy/AI/risk/approval/MT5/timestamp/account/mode).
- **AUTO_REAL_FULL** requires multiple env flags (`ALLOW_REAL_TRADING` + `ALLOW_AUTO_REAL_FULL` + no `EMERGENCY_STOP`); default off.

## Essential Files (start here)

1. `backend/app/core/config.py` — all configuration + safety flags
2. `backend/app/domain/ports.py` — the port contracts
3. `backend/app/risk/engine.py` — risk decisions
4. `backend/app/execution/order_service.py` — the order chokepoint
5. `backend/app/bridge/mock_bridge.py` — Phase 1 bridge
6. `backend/app/persistence/entities.py` — DB schema
7. `backend/app/main.py` — app wiring
8. `backend/app/ai/service.py` — advisory AI/MCP runtime chokepoint
9. `backend/app/market_data/` — external watchlist providers and config
