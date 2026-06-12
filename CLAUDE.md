# CLAUDE.md

> เป้าหมาย: เป็น "ความจำถาวร" ของโปรเจกต์ ที่ Claude Code อ่านอัตโนมัติทุก session
> กฎเหล็ก: เก็บให้ < 5,000 tokens เพราะทุกบรรทัดถูกอ่านซ้ำทุกข้อความ

---

## 1. สรุปโปรเจกต์ (Project Summary)
- ชื่อโปรเจกต์/ชื่อแอป: **ทางรอด**
- ทำอะไร: เว็บแอป trading เชื่อม **MetaTrader 5** รองรับ manual + auto trading เริ่มที่ **XAUUSD** (ขยาย symbol อื่นได้) เน้น **safety-first**
- สถานะปัจจุบัน: **Phase 1 safety foundation + Phase 2 proposal foundation** — มี editable MT5 config, approval queue, D40/D20 config + manual proposals; ยังไม่พร้อม live MT5/เงินจริง; ดู `PHASE_TRACKER.md`

## 2. โหมดงาน (Work Modes)

### 🌐 Frontend / Web
- เฟรมเวิร์ก/ภาษา: **Vue 3 + Vite + TypeScript** (vue-router, Pinia, axios)
- โฟลเดอร์หลัก: `frontend/src/`
- Dev / Build: `npm run dev` / `npm run build` (ใน `frontend/`)
- กฎเฉพาะ: แยก page/component, เรียก API ผ่าน `src/api/client.ts` เท่านั้น, real-account order ต้องมี confirmation modal

### ⚙️ Backend / API
- ภาษา/เฟรมเวิร์ก: **Python 3.14 + FastAPI** (SQLAlchemy 2, Alembic, pydantic v2)
- โฟลเดอร์หลัก: `backend/app/`
- Run / Test: `uvicorn app.main:app --reload` / `pytest`
- กฎเฉพาะ:
  - **ทุก order วิ่งผ่าน `app/execution/order_service.py` ที่เดียว** (manual + auto) — ห้ามยิง bridge ตรงจากที่อื่น
  - แยก concern เด็ดขาด: UI / execution / risk / AI prompt / MT5 bridge / strategy ไม่ปนกัน (ports & adapters ใน `app/domain/ports.py`)
  - Risk Engine คืน `ALLOW / WARN / BLOCK` + reasons[] เสมอ
  - ห้าม hardcode risk/lot/account type/trading mode — อ่านจาก `app/core/config.py` (env)

### 📊 Data / Memory (markdown)
- ที่อยู่: `memory/` (strategy, risk, news, user-rules, system, skills)
- กฎเฉพาะ: ไฟล์เล็ก แยกหมวด; AI อ่านก่อนวิเคราะห์ และอัปเดตเมื่อมีประโยชน์; **ห้าม AI เขียนทับ critical risk rule เองโดยไม่ขออนุมัติ**

## 3. โครงสร้างที่ควรรู้ (Key Structure)
- `backend/app/domain/` = models + ports (pure, ไม่มี framework)
- `backend/app/risk/` = Risk Engine (ด่านตัดสินใจกลาง)
- `backend/app/execution/` = order chokepoint + idempotency + state machine + audit
- `backend/app/bridge/` = MT5 abstraction + `mock_bridge` (default) + `ea_socket_bridge`
- รายละเอียดเต็ม ดู `PROJECT_STRUCTURE.md`

## 4. Conventions ร่วม (ใช้ทุกโหมด)
- การตั้งชื่อ: identifier เป็นภาษาอังกฤษ, snake_case (Python) / camelCase (TS), ไฟล์ Vue = PascalCase
- ภาษาใน commit / comment: ไทยหรืออังกฤษก็ได้ แต่ comment อธิบาย "ทำไม" ไม่ใช่ "ทำอะไร"
- **ห้ามทำ:** เปิด real auto trading เป็น default · ให้ AI ยิง order ตรง · ยิง order โดยไม่ผ่าน Risk Manager · order ไม่มี idempotency key/audit log · hardcode ค่า risk/lot/account/mode
- **ต้องทำ:** ไม่รู้ demo/real → block · bridge ไม่พร้อม → block · ข่าวแรงใกล้ → block · config หาย → block · ทุก order มี idempotency key + audit log

## 5. คำสั่งที่ใช้บ่อย (Commands)
```bash
# backend setup: cd backend && pip install -e . && alembic upgrade head
# backend run:   cd backend && uvicorn app.main:app --reload
# backend test:  cd backend && pytest
# frontend:      cd frontend && npm install && npm run dev
```

## 6. Known Issues / Gotchas
- Default ยังใช้ **mock bridge** — `ea_socket` และ MQL5 EA มี implementation แล้ว แต่ยังไม่ผ่าน MetaEditor compile/demo soak test (กฎ: bridge ไม่พร้อม → block)
- MT5 account/bridge config แก้ได้จาก UI และเก็บใน DB; app ไม่รับ/ไม่เก็บ password และ login/server/type ไม่ตรง → block
- DB dev = SQLite (`DATABASE_URL` ว่าง = ใช้ default sqlite), prod = PostgreSQL
- safety flags (`ALLOW_REAL_TRADING`, `ALLOW_AUTO_REAL_FULL`, `EMERGENCY_STOP`) ต้องตั้งครบหลายตัว auto-real ถึงทำงาน — default ปิดหมด

## 7. TODO หลัก (เป้าใหญ่)
- Phase 2: AI provider (Claude+failover), News + risk score, นิยาม/implement D40/D20 signal จริง
- Phase 3: full scheduler, auto-demo exec, real-approval queue, trade history (R), loss review, markdown memory เต็ม, MQL5 demo validation + persistent recovery, retry/circuit breaker, Docker/deploy

---
<!-- อัปเดตเมื่อ stack/convention เปลี่ยน; อย่าใส่ log หรือบทสนทนาเก่า -->
