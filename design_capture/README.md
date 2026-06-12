# Design Capture — ทางรอด (Thang Rod)

> สแน็ปช็อตของ **เมนูและฟีเจอร์ทั้งหมด** ในแอป ดึงจากซอร์สโค้ดจริง
> (`frontend/src/`) ณ 2026-06-12 — ใช้เป็น reference สำหรับงาน redesign
>
> ไม่ใช่ภาพหน้าจอ แต่เป็น "inventory" ที่ละเอียดกว่า: โครงเมนู, ทุก panel,
> ทุก control, ข้อมูลที่แสดง, สถานะ (loading/empty/error), endpoint ที่เรียก
> และข้อความ safety — ทุกอย่างที่นักออกแบบต้องรู้เพื่อจัดวางใหม่

## ไฟล์ในโฟลเดอร์นี้

| ไฟล์ | เนื้อหา |
|---|---|
| [01_navigation.md](01_navigation.md) | โครง sidebar 3 กลุ่ม + topbar safety strip + global shell |
| [02_pages.md](02_pages.md) | ทั้ง 11 หน้า: purpose, panels, controls, data, states, API |
| [03_components.md](03_components.md) | component ใช้ซ้ำ (watchlist, countdown, badges, modal, ฯลฯ) |
| [04_design_tokens.md](04_design_tokens.md) | สี/ฟอนต์/spacing/radius tokens (OKLCH, light+dark) |

## ภาพรวมแอป

- **ชื่อ:** ทางรอด — เว็บเทรดเชื่อม MetaTrader 5, **safety-first**, เริ่มที่ XAUUSD
- **Stack UI:** Vue 3 + Vite + TypeScript, vue-router, Pinia, axios
- **ธีม:** light + dark สลับได้ (ปุ่มบน topbar), สีเป็น OKLCH ผ่าน CSS tokens
- **เลย์เอาต์:** sidebar ซ้ายคงที่ (244px) + content กลางกว้างสุด 1120px
- **หลักดีไซน์ (จาก DESIGN.md):** "Calm, trustworthy, precise" — ตัวเลขใช้ mono
  tabular, verdict ความปลอดภัย (ALLOW/WARN/BLOCK) นำสายตาเสมอ

## ปรัชญาที่ UI ต้องสะท้อน (อย่าทิ้งตอน redesign)

1. **Verdict ความปลอดภัยมาก่อน** — ทุกหน้าที่เกี่ยวกับ order ต้องโชว์
   ALLOW/WARN/BLOCK เด่นชัด พร้อมเหตุผล
2. **AI เป็น advisory เท่านั้น** — ทุกที่ที่มี AI ต้องมีข้อความกำกับว่าไม่ตัดสิน/ไม่ยิง order
3. **Real account = ต้องยืนยัน 2 ชั้น** (confirm modal + approval queue)
4. **ไม่โชว์/ไม่กรอกความลับ** — secret แสดงเป็นชื่ออ้างอิง env เท่านั้น
5. **สถานะ "ไม่พร้อม" ต้องเห็นชัด** — bridge unhealthy, feed unavailable, mock data
   ต้องมี badge/notice เตือน ไม่ทำเนียนว่าใช้ได้

## ความรับผิดชอบของแต่ละเมนู (สรุป 1 บรรทัด)

| เมนู | หน้าที่ |
|---|---|
| Dashboard | ภาพรวม account/risk/workflow + watchlist realtime |
| Manual Order | ตั๋วสั่งซื้อผ่าน Risk Manager + preview + approve |
| Strategy | ตั้งค่า preset D40/D20, สร้าง proposal, backtest |
| Approvals | คิวอนุมัติ order (real/warn) พร้อม risk + AI context |
| Risk Monitor | verdict + facts + limits ปัจจุบัน |
| History | trade ปิดแล้ว: P&L, R-multiple, รายวัน, loss review |
| AI Analysis | รัน advisory analysis + ดู provenance |
| Logs | audit trail / risk decisions / system |
| MT5 Account | สถานะ + ตั้งค่า bridge/account allowlist |
| Providers | จัดการ AI/MCP provider + capability routing |
| Market Data | ตั้งค่า feed ราคา realtime (MT5/Alpaca) |
