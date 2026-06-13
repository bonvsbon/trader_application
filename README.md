# ทางรอด

เว็บแอปเทรดแบบ Safety-first เชื่อมต่อ MetaTrader 5 รองรับ Manual Trading,
Trade Proposal และระบบวิเคราะห์ด้วย AI/MCP โดยเริ่มต้นที่ XAUUSD

> **สถานะปัจจุบัน:** Mock/Demo flow และระบบวิเคราะห์พร้อมใช้งานสำหรับพัฒนา
> แต่ Live MT5 และการเทรดเงินจริงยังไม่พร้อมใช้งาน Production

## เริ่มใช้งาน

บน Windows ให้รันจากโฟลเดอร์โปรเจกต์:

```powershell
.\start-app.ps1
```

จากนั้นเปิด:

- Web App: [http://localhost:5173](http://localhost:5173)
- API: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- API Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

เมื่อต้องการ restart ทั้ง Backend และ Frontend:

```powershell
.\start-app.ps1 -Restart
```

สคริปต์จะตรวจ dependency, รัน database migration และเปิด service ที่จำเป็นให้
โดยอัตโนมัติ

## ฟีเจอร์ที่มีแล้ว

- Dashboard พร้อม workflow status และ realtime watchlist
- Manual Order ที่ผ่าน Risk Engine และ OrderService
- Approval Queue สำหรับคำสั่งที่ต้องยืนยัน
- ตั้งค่า MT5 account และ bridge ได้จากหน้าเว็บ
- กลยุทธ์ XAUUSD D40/D20 และ Trade Proposal
- Trade History, P&L, R multiple และ loss review
- Local LLM ผ่าน Ollama + Open WebUI
- MCP Provider พร้อม tool allowlist และ capability mapping
- OpenAI Responses API เป็น cloud fallback แบบปิดไว้เป็นค่าเริ่มต้น
- Provider routing, runtime failover และ periodic health check
- Realtime watchlist ผ่าน MT5 หรือ Alpaca
- PostgreSQL สำหรับฐานข้อมูลหลัก
- User login foundation โดยใช้ MT5 login เป็น username

ดูสถานะทั้งหมดที่ [PHASE_TRACKER.md](PHASE_TRACKER.md)

## หลักความปลอดภัย

ทุก Order ต้องผ่านเส้นทางเดียว:

```text
UI / Strategy / Workflow
  -> OrderService
  -> Risk Engine
  -> Approval Gate
  -> MT5 Bridge
  -> Audit Log
```

กฎสำคัญ:

1. AI และ MCP ไม่มีสิทธิ์ส่ง Order โดยตรง
2. ทุก Order ต้องมี idempotency key และ audit log
3. Account type ไม่ชัดเจนต้อง BLOCK
4. Bridge ไม่พร้อมหรือข้อมูลสำคัญหายต้อง BLOCK
5. Real Trading และ Auto Real ปิดเป็นค่าเริ่มต้น
6. Password ของ MT5 ต้องอยู่ใน MT5 Terminal เท่านั้น
7. API key เก็บใน environment variable ไม่เก็บในฐานข้อมูล

จุดควบคุม Order หลักอยู่ที่:
`backend/app/execution/order_service.py`

## เมนูตั้งค่าหลัก

### MT5 Account

ใช้ตั้งค่า bridge, login, server และ account type

ระบบไม่รับและไม่เก็บ MT5 master password

### Analysis Providers

ใช้ตั้งค่า:

- Local LLM ผ่าน Open WebUI
- MCP Streamable HTTP หรือ SSE
- OpenAI cloud fallback
- Capability routing และ provider priority
- Tool allowlist และ capability-to-tool mapping
- Connection test และ health check

รายละเอียด Local AI อยู่ที่ [LOCAL_AI_SETUP.md](LOCAL_AI_SETUP.md)

### Market Data

เลือก realtime watchlist provider:

- `mt5`
- `alpaca`
- `disabled`

Alpaca ใช้สำหรับ watchlist และ analysis เท่านั้น ราคา Risk และ Execution
ยังต้องมาจาก MT5 เพื่อป้องกัน feed mismatch

## Tech Stack

| ส่วน | เทคโนโลยี |
|---|---|
| Frontend | Vue 3, Vite, TypeScript, Pinia, Axios |
| Backend | Python 3.14, FastAPI, SQLAlchemy 2, Alembic |
| Database | PostgreSQL, SQLite fallback สำหรับ isolated dev |
| AI | Open WebUI, Ollama, MCP Python SDK, OpenAI Responses API |
| Trading | MetaTrader 5, MQL5 EA, TCP socket bridge |

## ตั้งค่าแบบ Manual

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,postgres]"
Copy-Item ..\.env.example ..\.env
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

เปิด Terminal อีกหน้าหนึ่ง:

```powershell
cd frontend
npm install
npm run dev
```

## ตรวจสอบคุณภาพ

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests

cd ..\frontend
npm run type-check
npm run build
```

ผลตรวจล่าสุด:

- Backend tests: `136 passed`
- Ruff: passed
- Frontend type-check: passed
- Frontend production build: passed
- Alembic: `0011_identity_foundation`

## First Owner Setup

เมื่อเปิด `USER_AUTH_ENABLED=true` การเข้าเว็บครั้งแรกจะแสดงหน้าสร้างเจ้าของระบบ:

- Username ใช้หมายเลข MT5 login
- ระบุ MT5 server และ account type ให้ตรงกับบัญชีจริง
- ตั้ง App Password ใหม่สำหรับใช้กับทางรอด

ห้ามใช้ Broker/MT5 master password เป็น App Password

ปัจจุบันระบบอนุญาตเฉพาะ First Owner ระหว่างที่ข้อมูลการเทรดยังอยู่ในขั้นตอน
ปรับให้รองรับหลายบัญชีอย่างปลอดภัย

## เอกสารเพิ่มเติม

- [PHASE_TRACKER.md](PHASE_TRACKER.md): สถานะและงานที่ยังเหลือ
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md): โครงสร้างโปรเจกต์
- [LOCAL_AI_SETUP.md](LOCAL_AI_SETUP.md): ตั้งค่า Ollama, Open WebUI, MCP และ OpenAI
- [OPERATIONS.md](OPERATIONS.md): การรันและดูแลระบบ
- [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md): Production release gates
- [requirements.md](requirements.md): Product requirements
- [rule.md](rule.md): กฎความปลอดภัย

## ข้อจำกัดปัจจุบัน

- MQL5 EA compile ผ่านและ authenticated DEMO read/reconnect soak ผ่านแล้ว;
  execution/reconciliation soak ยังไม่ครบ
- Free official-US calendar จาก New York Fed + Federal Reserve เชื่อมจริงแล้ว
  โดยไม่ใช้ API key พร้อม cache และ stale/failure fail-closed;
  MT5 volatility/session adapter ยังต้องยืนยัน `is_live=true` ช่วงตลาดเปิด
- Auto-demo workflow พร้อมแบบ opt-in (`WORKFLOW_AUTO_DEMO_ENABLED=false`
  โดย default) และ dedupe ต่อ closed signal bar แล้ว แต่ยังไม่เปิด live soak
- Alpaca และ OpenAI ต้องใช้ credential ของผู้ใช้เพื่อทดสอบจริง
- Docker Compose ยังต้องทดสอบบนเครื่องที่มี Docker
- ห้ามเปิด Real Trading จนกว่า Production Readiness Checklist จะผ่านครบ
