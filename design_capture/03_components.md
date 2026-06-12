# 03 · Shared Components & UI Primitives

Source: `frontend/src/components/*.vue`, shared classes in `frontend/src/style.css`

## IntervalCountdown (`components/IntervalCountdown.vue`)
ตำแหน่ง: ล่างสุดของ sidebar. หน้าที่: คุม interval workflow scheduler.
- หัว: "Workflow" + run-state dot (Running เขียว / Stopped เทา)
- ตัวเลข **MM:SS** countdown ขนาดใหญ่ (mono)
- บรรทัด current step (capitalize) / "Idle"
- **backoff notice** (warn): "Backing off after N failed cycles · retry in Xs"
- ปุ่ม: Start (เขียว) / Stop (danger) สลับตามสถานะ + "Run now" (secondary)
- error line (block) ถ้ามี last_error / action error
- ข้อมูล: `ws /ws/status` (1s) + fallback poll `GET /api/workflow/status` (2s);
  actions `POST /api/workflow/start|stop|run`

## RealtimeWatchlist (`components/RealtimeWatchlist.vue`)
ตำแหน่ง: ท้าย Dashboard. หน้าที่: stream quote แบบ read-only.
- หัว: "Realtime Watchlist" + copy "Execution still uses the MT5 broker quote" +
  connection badge `{source} · {feed_status}` (HEALTHY) / "RECONNECTING"
- symbol input + ปุ่ม "Apply symbols" (สูงสุด 25 symbol)
- **warn-notice** เมื่อ source = `mt5:mock`: "synthetic test data, not live prices"
- ตาราง: Symbol, **Bid (มีสี tick ▲ ขึ้น / ▼ ลง เทียบ bid ก่อนหน้า)**, Ask, Spread, Updated
- error list ต่อ symbol
- ข้อมูล: `ws /ws/market?symbols=…`, auto-reconnect 3s
- หมายเหตุ redesign: mock bridge ตอนนี้ส่ง simulated live tick (ขยับจริง) แต่
  ราคา execution ไม่เปลี่ยน — ป้าย mock ต้องคงไว้

## UI primitives (global classes ใน style.css)

### Badge — state → สี (ผูกจากค่า API ตรง ๆ ผ่าน `:class`)
| กลุ่ม | ค่า | สี |
|---|---|---|
| ดี/อนุญาต | ALLOW, HEALTHY, DEMO, FILLED, APPROVED, ok | เขียว (allow) |
| เตือน/รอ | WARN, PENDING_APPROVAL, PENDING, SUBMITTED, RECONCILIATION_REQUIRED | เหลือง (warn) |
| บล็อก/อันตราย | BLOCK, UNHEALTHY, UNKNOWN, REAL, RISK_BLOCKED, ERROR, REJECTED, CANCELLED | แดง (block) |
- มี dot นำหน้า (ปิดด้วย `.no-dot`), ขนาดใหญ่ `.lg`
- **สำคัญ:** REAL = แดง (เจตนา เพื่อเตือนบัญชีจริง), DEMO = เขียว

### Button — `.btn` + variant
`(default=accent)`, `.secondary`, `.ghost`, `.danger`; ขนาด `.sm`, เต็มกว้าง `.full`;
spinner `.spin`; disabled = จาง; touch ≥44px

### Panel / layout
- `.panel` (surface + border + radius-lg + shadow-sm), `.pad-tight`
- `.panel-head` + `.panel-title` (uppercase เล็ก)
- `.grid` = auto-fit minmax(248px,1fr)
- `.kv` = แถว label/value (label muted, value ขวา); `.mono` ตัวเลข tabular

### Forms
input/select/textarea เต็มกว้าง, focus = ขอบ accent + ring; `.field` + label muted;
number ใช้ฟอนต์ mono

### Table
`.table-wrap` (scroll-x); thead sticky, ตัวเลขชิดขวา mono (`td.num`)

### Reasons list
`.reasons` (จุดแดง block) / `.reasons.warn` (จุดเหลือง) — ใช้โชว์ risk reasons/warnings

### States
- **Loading:** `.skeleton .sk-line` (shimmer)
- **Empty:** `.empty` (icon + title + คำอธิบาย muted)
- **Notice:** `.notice` (block bg) / `.notice.success` (allow) / `.notice.warn` /
  `.notice.neutral`

### Modal
native `<dialog class="modal">` — focus-trap + Esc + top-layer ฟรี; backdrop blur;
ใช้ที่ confirm real-account order

### Directional value
`.pos` (เขียว) / `.neg` (แดง) — คู่กับเครื่องหมาย +/− สำหรับ P&L และ R-multiple

### Motion
transition tokens `--dur*`/`--ease`; เคารพ `prefers-reduced-motion`
