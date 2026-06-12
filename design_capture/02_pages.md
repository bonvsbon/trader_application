# 02 · Pages & Features

ทั้ง 11 หน้า แต่ละหน้า: **purpose · panels/sections · controls · data · states · API · safety**
Source: `frontend/src/pages/*.vue`

---

## 1. Dashboard — `/dashboard` (`DashboardPage.vue`)
**Purpose:** account, risk, และ workflow ในหน้าเดียว
- **Risk hero panel** (นำสายตา): "Trade readiness" + badge ALLOW/WARN/BLOCK ขนาดใหญ่;
  reasons (block) / warnings (warn) เป็น list; เส้นขอบ panel เปลี่ยนสีตาม decision
- **Grid 4 panels:**
  - Connection — Bridge health, Account type, Mode
  - Account — Balance, Equity, Free margin %
  - Quote (`{symbol}`) — Bid, Ask, Spread pts (ถ้ามี quote)
  - Activity — Open positions, Trades today, High-impact news (Clear/Near/Unavailable),
    Volatility feed (Normal/Abnormal/Unavailable)
- **RealtimeWatchlist** component (ดู 03)
- **States:** loading skeleton; error → notice + ปุ่ม Retry ("Backend did not respond on
  port 8000"); auto-retry ทุก 8s
- **API:** `GET /api/dashboard`

---

## 2. Manual Order — `/order` (`ManualOrderPage.vue`)
**Purpose:** ตั๋วสั่งซื้อมือ ทุกตั๋ววิ่งผ่าน Risk Manager ก่อนถึง broker
- **Order ticket panel:** account-type badge; ฟิลด์ Symbol, Side (BUY/SELL), Volume (lots),
  Risk %, Stop loss (required), Take profit (optional)
  - ปุ่ม **"Check size and risk"** (preview)
  - ปุ่ม **"Submit order"** (demo) / **"Review real-account order"** (real)
  - hint บอกความต่าง demo (fill ทันทีถ้าผ่าน) vs real (confirm → approve)
- **Risk preview panel:** decision badge + Entry, Estimated loss, Estimated reward,
  Actual risk %, Max lot for risk, Projected portfolio risk + reasons/warnings
- **Result panel:** decision + state badges, message, reasons/warnings
  - state `PENDING_APPROVAL` → ปุ่ม Approve and execute / Reject order
  - state `RECONCILIATION_REQUIRED`/`SUBMITTED` → ปุ่ม Reconcile with MT5
- **Empty state:** "No order submitted yet"
- **Real-account confirm modal** (danger): ยืนยันก่อน แล้วยังต้อง approve อีกชั้น
- **API:** `GET /api/account`, `POST /api/risk/preview`, `/api/orders/submit|approve|reject|reconcile`
- **Safety:** real → confirm modal; ทุกตั๋วผ่าน Risk Manager; SL บังคับ

---

## 3. Strategy & Proposals — `/strategy` (`StrategyPage.vue`)
**Purpose:** ตั้งค่า preset XAUUSD D40/D20, สร้าง proposal, backtest
- **Preset Configuration panel:** Enabled toggle; Symbol, Preset name, D40 value,
  D20 value, Reward/risk, Risk %; toggle "Require news filter clear"; toggle
  "Confirm signal definition (enables automatic D40/D20 evaluation)";
  warn-notice อธิบายว่า D40/D20 = Donchian breakout
  - ปุ่ม **"Evaluate D40/D20 now"** (disabled จนกว่า enabled + signal confirmed)
  - ปุ่ม **"Save preset"**
- **Manual Proposal Builder panel:** Side, Stop loss, Volume (optional, auto-size),
  Setup reason (textarea); ปุ่ม "Generate risk-checked proposal"
- **Signal Backtest panel:** input จำนวน candle + ปุ่ม "Run backtest";
  cards: Trades (W/L/open), Win rate, Total R, Avg R, Max drawdown;
  warn-notice "idealized rule check … not a profitability forecast"
- **Recent Proposals table:** Created, Setup (side+symbol), Entry, SL, TP, Lot,
  Risk badge, Status badge, ปุ่ม Submit (เฉพาะ DRAFT) → confirm() ก่อนส่ง
- **API:** `GET/PUT /api/strategy/configuration`, `GET/POST /api/proposals`,
  `POST /api/strategy/evaluate-signal`, `POST /api/strategy/backtest`,
  `POST /api/proposals/{id}/submit`
- **Safety:** auto-signal gated หลัง `signal_definition_confirmed`; proposal-only
  ไม่ยิง broker; backtest read-only + disclaimer

---

## 4. Approval Queue — `/approvals` (`ApprovalsPage.vue`)
**Purpose:** คิว order ที่รอคนอนุมัติ (real/warn) — ตัดสินใจโดยเห็น context ครบ
- **Approval cards** (1 ใบ/order):
  - Header: side (สี BUY/SELL) + symbol + account badge + decision badge + เวลา
  - Facts grid: Volume, Stop loss, Take profit, Risk %, Requested by
  - **"Why this needs approval":** risk reasons (block list) + warnings (warn list)
  - **"Strategy & AI context":** badge `Proposal #id`; Setup (strategy reason);
    AI summary + confidence %; ข้อความ "AI is advisory only…"
  - Actions: Reject (danger) / Approve → ทั้งคู่ confirm() ก่อน
- **Empty state:** "No orders awaiting approval"
- **API:** `GET /api/orders/pending-approval`, `POST /api/orders/approve|reject`
- **Safety:** risk ถูก recheck ตอน approve; AI advisory only

---

## 5. Risk Monitor — `/risk` (`RiskMonitorPage.vue`)
**Purpose:** verdict สดของ probe order XAUUSD + ข้อเท็จจริงเบื้องหลัง
- **Current verdict hero:** badge ALLOW/WARN/BLOCK + reasons/warnings (ขอบสีตาม decision)
- **Current facts panel:** Bridge, Account, Spread pts, Free margin %, Open positions,
  Trades today, High-impact news, Volatility feed
- **Configured limits panel:** Max risk/trade, Max open positions, Max trades/day,
  Max spread, Max order volume, Daily max loss
- **Safety problems panel** (เฉพาะเมื่อมี): config_problems + data_problems
- **API:** `GET /api/risk/status`

---

## 6. Trade History — `/history` (`HistoryPage.vue`)
**Purpose:** trade ที่ปิดแล้ว: realized P&L + R-multiple
- **Summary cards:** Net P&L, Total R, Win rate (W·L), Avg R (rated count)
- **Trades table:** แถวกดขยายได้ (caret) → journal: Exit reason, Opened, Volume,
  Risk decision, Strategy reason, AI note; คอลัมน์ Entry/Exit/P&L/R สีตามบวกลบ
- **By day panel:** Date, Trades, W/L, Net P&L, R ต่อวัน
- **Loss review panel:** รายการ trade ขาดทุน → textarea note + ปุ่ม "AI draft"
  (ดึงจาก loss_review capability, แก้ได้) + "Save review"; แสดง badge Reviewed
- **Header actions:** "Backfill 30d", "Refresh"
- **States:** loading skeleton, empty "No closed trades yet"
- **API:** `GET /api/history/trades|summary|daily|review`,
  `POST /api/history/backfill`, `/api/history/review/{ticket}`, analyze-review

---

## 7. AI Analysis — `/analysis` (`AIAnalysisPage.vue`)
**Purpose:** รัน advisory analysis ผ่าน provider route + ดู provenance (advisory-only)
- **Input panel:** Capability select (news_search, economic_calendar, chart_market,
  volatility_session, proposal_explanation, loss_review); Prompt (textarea);
  Context JSON (textarea, mono); ปุ่ม "Run advisory analysis"
- **Result panel:** badge AVAILABLE/NO PROVIDER; summary; Provider, Model/tool,
  Correlation id
- **Recent Analysis Attempts table** (provenance): Time, Capability, Provider,
  Model/tool, Status (OK/FAILED), Detail
- **API:** run analysis, `GET` snapshots
- **Safety:** prompt ตั้งต้น "Do not place an order"; เป็น advisory ล้วน

---

## 8. Logs — `/logs` (`LogsPage.vue`)
**Purpose:** audit trail (append-only), risk decisions, system events
- **Tabs:** Audit trail · Risk decisions · System
  - Audit table: Time, Event, Symbol, Decision, Account, Approval
  - Risk table: Time, Symbol, Decision, Reasons
  - System table: Time, Level (badge ERROR/WARNING), Source, Message
- **States:** loading skeleton, empty "Nothing logged yet"
- **API:** `GET /api/logs/audit`, `/api/logs/risk`, `/api/logs`

---

## 9. MT5 Account — `/account` (`Mt5AccountPage.vue`)
**Purpose:** สถานะการเชื่อมต่อ + ตั้งค่า bridge/account allowlist (แก้ได้)
- **Connection panel:** Bridge health, Config match (MATCH/MISMATCH), Last heartbeat,
  Detail, configuration_problems list
- **Connected Account panel:** account-type badge, Login, Server, Balance, Equity,
  Free margin (+%), Leverage
- **Runtime Configuration panel:** Enabled toggle; Bridge type (mock / ea_socket);
  Backend listen host/port; Request timeout; Heartbeat max age; Expected MT5
  login/server/account type; neutral-notice "password never stored / EA shared
  secret via env"
  - ปุ่ม "Test current connection" + "Save and restart bridge" (confirm())
  - validation: ea_socket ต้องมี login+server+DEMO/REAL
- **API:** `GET /api/account`, `/api/account/configuration`; `PUT` config;
  `POST /api/account/configuration/test`
- **Safety:** เลือก REAL ไม่ได้เปิดเทรดจริง (ยังต้อง safety flags); ไม่รับ password

---

## 10. Analysis Providers — `/settings/providers` (`AnalysisProvidersPage.vue`)
**Purpose:** จัดการ AI/MCP provider + capability routing
- **Providers list panel** + ปุ่ม "New"
- **Provider Configuration editor:** Display name; Provider type (mcp/claude/openai/local);
  Transport (Streamable HTTP / SSE legacy); Priority; Endpoint; Open WebUI model;
  web-search toggle; Secret environment reference; Timeout
  - **Capability Tool Mapping:** จับคู่แต่ละ capability → allowed tool
  - **Allowed tool IDs** (textarea, บรรทัดละ 1) — deny-by-default
  - test connection → discovered tools/models, health, latency
- **Active Capability Routing panel:** ลำดับ provider ต่อ capability (ตาม priority)
- **API:** analysis-providers CRUD/test/metadata/routing
- **Safety:** secret เก็บแค่ชื่อ env ref; MCP host allowlist + HTTPS for remote

---

## 11. Market Data — `/settings/market-data` (`MarketDataSettingsPage.vue`)
**Purpose:** ตั้งค่า feed ราคา realtime สำหรับ watchlist
- **Form:** Provider (MT5 broker feed / Alpaca stocks / Disabled); Enabled toggle;
  WebSocket endpoint; Feed (IEX realtime / SIP realtime / Delayed SIP);
  Feed status (read-only: broker-realtime / realtime-single-exchange /
  realtime-consolidated / delayed-consolidated); API key & secret environment
  references; Default symbols (comma); Maximum symbols; Connection timeout
  - ปุ่ม Test connection (รายงาน provider/feed_status/latency)
- **Safety:** Alpaca = watchlist/analysis เท่านั้น; ราคา risk/execution ยังมาจาก MT5
  เสมอ; key เก็บเป็น env ref

---

## ตารางสรุป page → API

| Page | Endpoints หลัก |
|---|---|
| Dashboard | `GET /api/dashboard` |
| Manual Order | `/api/account`, `/api/risk/preview`, `/api/orders/*` |
| Strategy | `/api/strategy/*`, `/api/proposals/*` |
| Approvals | `/api/orders/pending-approval`, `/approve`, `/reject` |
| Risk Monitor | `/api/risk/status` |
| History | `/api/history/*` |
| AI Analysis | analysis run + snapshots |
| Logs | `/api/logs/*` |
| MT5 Account | `/api/account/*` |
| Providers | `/api/settings/analysis-providers/*` |
| Market Data | `/api/settings/market-data` + `ws /ws/market` |
