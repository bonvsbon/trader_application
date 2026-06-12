# EA Socket Multi-User Authentication Plan

Last updated: 2026-06-12

## Implementation Status

- `[x]` Phase A foundation: `users`, `mt5_accounts`, hashed browser sessions,
  CSRF protection, lockout, first-owner bootstrap, MT5-login username, and
  ownership binding for the editable MT5 config
- `[x]` Protected HTTP APIs and WebSockets require the browser session when
  `USER_AUTH_ENABLED=true`
- `[x]` EA socket configuration must match the logged-in owner's MT5 login,
  server, and DEMO/REAL type
- `[~]` Multiple users remain intentionally disabled until Phase B account
  scoping is complete; accepting more users now could expose global trading data
- `[ ]` Phase B account-scoped trading persistence
- `[ ]` Phase C multi-connection `BridgeRegistry`
- `[ ]` Phase D per-device EA pairing/token authentication

The application password is separate from the broker/MT5 password. The broker
password remains only inside MetaTrader 5 Terminal.

## เป้าหมาย

ให้ผู้ใช้แต่ละคน login เข้าแอป แล้วเห็นและสั่งงานได้เฉพาะ MT5 account ที่เป็นของตนเอง
โดย EA แต่ละตัวต้อง authenticate แยกกัน และทุก order ยังคงผ่าน Risk Engine กับ
`OrderService` เท่านั้น

ระบบจะไม่รับหรือเก็บ MT5 password ผู้ใช้ยัง login broker ภายใน MT5 Terminal เหมือนเดิม

## สถานะปัจจุบันและช่องว่าง

ปัจจุบันระบบเป็น single-user:

- Web API ใช้ bearer token เดียวจาก `API_AUTH_TOKEN`
- EA ทุกตัวใช้ `MT5_EA_SHARED_SECRET` ค่าเดียว
- `mt5_config` เป็น singleton
- `get_configured_bridge()` คืน bridge เดียวทั้ง process
- Socket listener รับ active connection ได้เพียงหนึ่งตัว
- Order, position, history, proposal และ workflow ไม่มี `user_id` หรือ `mt5_account_id`

โครงนี้ไม่ควรนำไปเปิด multi-user โดยเพิ่ม secret หลายค่าเพียงอย่างเดียว เพราะยังมีโอกาส
อ่านข้อมูลหรือส่ง order ข้ามบัญชี

## Architecture ที่แนะนำ

```text
Web user
  -> HTTPS login/session
  -> AuthContext(user_id, roles)
  -> Account authorization
  -> Account-scoped OrderService
  -> BridgeRegistry.get(mt5_account_id)

MT5 EA
  -> outbound TLS connection
  -> EA Gateway / ConnectionManager
  -> device authentication
  -> verify connected MT5 login/server/type
  -> bind connection to mt5_account_id
  -> BridgeRegistry
```

แยก authentication เป็นสองชั้น:

1. **User authentication**
   ระบุตัวผู้ใช้เว็บ ใช้ secure HTTP-only session หรือ OIDC/JWT
2. **EA device authentication**
   ระบุ EA installation แต่ละเครื่องด้วย device credential ที่แยกกัน หมุนและ revoke ได้

การที่ EA authenticate ผ่านไม่ได้หมายความว่าผู้ใช้เว็บมีสิทธิ์ในบัญชีนั้น
และการที่ผู้ใช้ login ผ่านไม่ได้หมายความว่าสามารถใช้ EA connection ใดก็ได้

## EA Enrollment และ Authentication

### Flow ที่แนะนำ

1. ผู้ใช้ login แล้วกด `Add MT5 Account`
2. Backend สร้าง pairing code แบบใช้ครั้งเดียว อายุ 5-10 นาที
3. ผู้ใช้ใส่ pairing code ใน EA หรือ local connector
4. EA เชื่อมต่อออกไปยัง gateway ผ่าน TLS
5. Backend ตรวจ pairing code และสร้าง `ea_device`
6. Backend อ่าน `account_info` จาก EA จริง
7. ผู้ใช้ยืนยัน login, server และ DEMO/REAL บนหน้าเว็บ
8. Backend ผูก `ea_device` เข้ากับ `mt5_account`
9. Pairing code ถูกทำลายและออก device token ระยะยาว

### Protocol v2

ตัวอย่าง client hello:

```json
{
  "type": "auth",
  "protocol_version": 2,
  "device_id": "uuid",
  "device_token": "ea_live_random-token",
  "client_nonce": "random",
  "timestamp": 1781164800
}
```

หลัง authenticate backend ต้องเรียก `account_info` และตรวจ:

- login ตรงกับ account ที่ผูกไว้
- server ตรงแบบ case-insensitive
- account type ตรงและไม่เป็น `UNKNOWN`
- device ยัง active และไม่ถูก revoke
- user/account ยัง active
- ไม่มี connection อื่นแย่ง execution lease

ข้อมูล login/server ที่ EA ส่งมาตอน auth เป็นเพียง claim ห้ามเชื่อจนตรวจด้วย RPC สำเร็จ

### Secret storage

- Pairing code เก็บเฉพาะ hash และมี expiry/use-once
- Device token เป็น random อย่างน้อย 256 bit และ DB เก็บเฉพาะ keyed hash
- รองรับ rotate/revoke ต่อ device
- ห้ามส่ง token ผ่าน raw TCP บน network ภายนอก
- Production ใช้ TLS gateway, private VPN หรือ local connector + mTLS
- Direct raw TCP อนุญาตเฉพาะ loopback/dev

ทางที่ปลอดภัยที่สุดในระยะ production คือ:

```text
EA --loopback socket--> Local Connector
Local Connector --TLS/mTLS WebSocket--> Backend Gateway
```

Local Connector สามารถเก็บ credential ใน Windows Credential Manager/macOS Keychain
แทนการเก็บ secret ระยะยาวใน EA input

## Data Model

เพิ่มตาราง:

- `users`
  `id`, `email`, `display_name`, `status`, `created_at`
- `user_identities`
  เก็บ subject จาก OIDC/auth provider
- `mt5_accounts`
  `id`, `owner_user_id`, `login`, `server`, `account_type`, `enabled`
- `ea_devices`
  `id`, `mt5_account_id`, `device_name`, `token_hash`, `status`,
  `last_seen_at`, `revoked_at`
- `ea_pairing_codes`
  hash, user, expiry, used timestamp
- `account_memberships`
  เตรียมรองรับ owner/operator/viewer ในอนาคต
- `workflow_configs`
  config และ scheduler state ต่อ MT5 account

เพิ่ม `user_id` และ `mt5_account_id` ให้ข้อมูลสำคัญ:

- orders และ dedupe fingerprint
- risk decisions และ audit logs
- positions และ closed trades
- trade proposals และ strategy config
- workflow runs
- analysis snapshots ที่เกี่ยวกับบัญชี
- MT5 runtime config

Unique constraints ต้อง scope ต่อ account:

- `(mt5_account_id, idempotency_key)`
- `(mt5_account_id, dedupe_fingerprint)`
- `(mt5_account_id, position_ticket)`
- `(mt5_account_id, closed_trade_ticket)`
- `(server_normalized, login)` สำหรับ MT5 account

## Backend Changes

### Authentication

- เปลี่ยน `get_operator()` เป็น `get_current_user()` ที่คืน `AuthContext`
- เพิ่ม roles ขั้นต้น: `owner`, `operator`, `viewer`
- ใช้ HTTP-only secure cookie สำหรับ browser
- API token คงไว้เฉพาะ automation/service account
- WebSocket ต้อง authenticate ก่อน subscribe

### Authorization

ทุก endpoint ที่แตะ trading data ต้องรับ `mt5_account_id` และตรวจ membership:

```text
/api/accounts/{account_id}/orders
/api/accounts/{account_id}/risk
/api/accounts/{account_id}/history
/api/accounts/{account_id}/workflow
```

Repository query ต้องมี account scope เสมอ ห้ามโหลด row ด้วย ID อย่างเดียว

### Bridge

แทน process singleton ด้วย:

```python
BridgeRegistry
  register(connection_session)
  get(mt5_account_id)
  revoke(device_id)
  disconnect(mt5_account_id)
```

ข้อกำหนด:

- รองรับหลาย socket connection พร้อมกัน
- หนึ่ง account มี execution connection หลักได้หนึ่งตัว
- connection ซ้ำต้อง BLOCK หรือรอ operator เลือก primary
- lock/RPC queue แยกต่อ connection ไม่ล็อกทั้งระบบ
- connection disconnect ทำให้ bridge health ของ account นั้นเป็น `UNKNOWN`
- restart backend ต้องให้ EA reconnect และ re-authenticate

### Order และ Risk

`OrderService` ต้องรับ:

```python
OrderService(
    session,
    bridge,
    account_context,
    actor_context,
)
```

ก่อน execute ต้องตรวจเพิ่ม:

- actor มีสิทธิ์ใน account
- request account ตรงกับ bridge session
- device/account binding ยัง valid
- connected login/server/type ยังตรง
- execution lease ยังเป็นของ connection นี้

Audit log ต้องบันทึก `user_id`, `mt5_account_id`, `ea_device_id`,
IP/session ID และ actor role

### Workflow

- scheduler แยกต่อ account
- ใช้ PostgreSQL advisory lock หรือ lease row ป้องกัน worker ซ้ำ
- workflow ของบัญชีหนึ่งห้ามใช้ bridge/config ของอีกบัญชี
- emergency stop รองรับ global และ per-account

## Frontend Changes

- Login/logout/session expiry
- Account switcher ที่แสดง login/server/type ชัดเจน
- `Add MT5 Account` pairing wizard
- หน้า EA Devices: connected, last seen, revoke, rotate credential
- route และ API ทุกหน้าผูก selected account
- ป้องกัน stale account selection หลัง logout/permission change
- REAL account confirmation ต้องแสดง owner, login และ server

## Implementation Phases

### Phase A - Identity Foundation

- เพิ่ม users, identities, memberships และ `AuthContext`
- รองรับ local admin migration เพื่อไม่ล็อกผู้ใช้เดิมออก
- เพิ่ม account ownership โดยยังใช้ bridge เดิม
- เพิ่ม authorization tests และ IDOR tests

Definition of done:
ผู้ใช้ A ไม่สามารถอ่านหรือแก้ config/order ของผู้ใช้ B ผ่าน API ได้

### Phase B - Account-Scoped Persistence

- เพิ่ม `mt5_account_id` ให้ตาราง trading ทั้งหมด
- backfill ข้อมูลเดิมเข้า default account
- เปลี่ยน unique constraints ให้ scope ต่อ account
- refactor repositories ให้ต้องระบุ account

Definition of done:
ข้อมูล order/history/position ของแต่ละ account แยกกันใน DB

### Phase C - Multi-Connection Bridge Registry

- แยก socket listener ออกจาก bridge handle
- เพิ่ม connection sessions และ registry
- RPC lock ต่อ connection
- duplicate connection policy และ execution lease
- health/metrics ต่อ account

Definition of done:
EA Demo สอง account เชื่อมพร้อมกันและอ่าน quote/account แยกกันได้

### Phase D - EA Protocol v2 และ Pairing

- เพิ่ม pairing endpoint และ device credential
- อัปเดต MQL5 EA ให้รองรับ protocol v2
- rotate/revoke token
- protocol version negotiation
- ปิด legacy shared secret ใน multi-user production

Definition of done:
EA ที่ token ผิด, revoke แล้ว หรือ account mismatch ถูกปฏิเสธและ audit ครบ

### Phase E - Account-Scoped Execution

- route, Risk Engine context และ `OrderService` ใช้ account context
- approval queue แยก account
- idempotency/reconciliation แยก account
- per-account emergency stop

Definition of done:
ทดสอบ concurrent order สอง account แล้วไม่มี bridge/data/idempotency ปะปนกัน

### Phase F - Frontend Multi-User UX

- login และ account switcher
- pairing/device management
- account-scoped dashboard/settings/history/logs
- role-based controls

Definition of done:
viewer ส่ง orderไม่ได้, operator ใช้งานเฉพาะ account ที่ได้รับสิทธิ์

### Phase G - Production Security

- TLS/mTLS gateway หรือ local connector
- session rotation, CSRF protection, rate limiting
- secret manager และ token pepper rotation
- device/user revocation propagation
- metrics, alerts และ penetration/IDOR test
- demo soak test หลาย account ก่อนเปิด REAL

## Files ที่คาดว่าจะเพิ่มหรือแก้

Backend:

- `app/api/auth.py`
- `app/api/deps.py`
- `app/api/routes/accounts.py`
- `app/api/routes/devices.py`
- routes trading ทั้งหมด
- `app/auth/models.py`
- `app/auth/service.py`
- `app/bridge/connection_manager.py`
- `app/bridge/session.py`
- `app/bridge/ea_socket_bridge.py`
- `app/bridge/base.py`
- `app/domain/models.py`
- `app/execution/order_service.py`
- `app/persistence/entities.py`
- `app/persistence/repositories.py`
- `app/workflow/scheduler.py`
- Alembic migrations ตั้งแต่ revision ถัดไป

EA/Connector:

- `mql5/ThangRodBridgeEA.mq5`
- `connector/` ถ้าเลือก production local connector

Frontend:

- `src/stores/auth.ts`
- `src/stores/account.ts`
- `src/pages/LoginPage.vue`
- `src/pages/AccountsPage.vue`
- `src/pages/EaDevicesPage.vue`
- `src/components/AccountSwitcher.vue`
- `src/api/client.ts`
- ทุก page ที่อ่านหรือเขียนข้อมูล account

## Release Gates

ห้ามเปิด multi-user REAL จนกว่าจะผ่านทั้งหมด:

- ไม่มี shared secret กลางตัวเดียวใน production
- ทุก trading row มี account ownership
- ทุก repository/API มี account authorization
- WebSocket แยกและ authenticate ตาม user/account
- EA token revoke มีผลทันที
- account switch ใน MT5 หลังเชื่อมทำให้ execution BLOCK
- duplicate EA connections ไม่สามารถส่ง order แข่งกัน
- idempotency และ reconciliation scope ต่อ account
- audit ระบุ user/account/device ครบ
- TLS/VPN/mTLS ผ่านการทดสอบ
- multi-account demo soak test ผ่าน

## ลำดับที่แนะนำ

เริ่ม Phase A และ B ก่อน ห้ามเริ่มจากแก้ EA ให้รับหลาย secret เพราะจะสร้างภาพว่า
รองรับ multi-user ทั้งที่ฐานข้อมูล, authorization และ `OrderService` ยังไม่แยก account

สำหรับการใช้งานจริง แนะนำทำ Local Connector ใน Phase D/G แต่สามารถเริ่ม MVP ด้วย
direct EA socket บน loopback/private network เพื่อทดสอบ Demo หลาย account ได้ก่อน
