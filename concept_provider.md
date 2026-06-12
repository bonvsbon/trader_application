# AI / Analysis Provider Concept

> สถานะสถาปัตยกรรม AI, MCP และ Market Data ของแอป **ทางรอด**
>
> Last updated: **2026-06-12**

## สถานะล่าสุด

ระบบ advisory analysis พร้อมใช้งานในระดับ application runtime แล้ว:

- `[x]` Provider registry, CRUD, health test และ capability routing
- `[x]` Local LLM ผ่าน Open WebUI พร้อม toggle เปิด/ปิด, model, web search และ tool IDs
- `[x]` MCP Streamable HTTP/SSE พร้อม tool discovery, allowlist และ capability-to-tool mapping
- `[x]` `AnalysisService` เป็นจุดเรียก AI/MCP กลาง
- `[x]` Runtime failover ตาม priority ของ provider
- `[x]` Analysis provenance บันทึก provider/model/tool, latency, success/error และ correlation ID
- `[x]` Secret และข้อมูลอ่อนไหวถูก redact ก่อนบันทึก snapshot
- `[x]` Proposal explanation, loss-review draft และ optional workflow analysis เชื่อม runtime แล้ว
- `[x]` หน้า AI Analysis สำหรับทดสอบ capability และดู provenance
- `[x]` Realtime watchlist รองรับ MT5 และ Alpaca แบบ config-driven
- `[x]` OpenAI Responses API cloud adapter แบบ config-driven และ default-off
- `[ ]` Claude cloud adapter
- `[ ]` Real economic calendar/news และ volatility/session adapter
- `[x]` Periodic provider health check แบบ stale-aware, batch-limited และ fail-isolated

Verification ล่าสุด:

- Backend tests: `136 passed`
- Ruff: passed
- Frontend TypeScript check: passed
- Frontend production build: passed
- Database migration: `0011_identity_foundation`
- PostgreSQL 16: migration verified through head on the local `trader` database
- Runtime API and MT5 mock watchlist WebSocket: verified

## กฎความปลอดภัย

AI และ MCP เป็น **advisory-only**:

1. ห้าม AI/MCP เรียก MT5 bridge หรือส่ง order
2. ทุก order ต้องผ่าน Risk Engine และ `OrderService`
3. Provider ไม่มีสิทธิ์เปลี่ยน risk rule, account mode หรือ safety flag
4. Secret เก็บใน environment เท่านั้น; DB/UI เก็บเพียงชื่อ `secret_ref`
5. MCP เรียกได้เฉพาะ tool ที่อยู่ใน `allowed_tools`
6. Enabled MCP provider ต้อง map ทุก capability ไปยัง tool ที่อนุญาต
7. Endpoint ใช้ exact host allowlist; remote endpoint ต้องเป็น HTTPS
8. AI explanation ล้มเหลวแล้ว manual/demo flow ยังทำงานต่อได้
9. Live news/volatility ที่เป็นข้อมูลบังคับสำหรับ real account ถ้าหายต้อง `BLOCK`

## Runtime Architecture

```text
Proposal / Workflow / Loss Review / AI Analysis page
  -> AnalysisService
  -> enabled + healthy providers for capability
  -> ordered by priority
  -> Local Open WebUI adapter or MCP tool
  -> validate and limit response
  -> persist one snapshot per attempt
  -> fail over to next provider when an attempt fails
```

`AnalysisService` อยู่ที่ `backend/app/ai/service.py` และเป็นจุดเรียก runtime กลาง
สำหรับ AI/MCP ทุกประเภท

### Capabilities

```text
news_search
economic_calendar
chart_market
volatility_session
proposal_explanation
loss_review
```

### Provider Configuration

Provider registry รองรับ:

- `provider_type`: `mcp | claude | openai | local`
- `enabled`
- `endpoint`
- `model_name`
- `web_search_enabled`
- `transport`: `streamable_http | sse`
- `secret_ref`
- `timeout_sec`
- `priority`
- `capabilities`
- `allowed_tools`
- `capability_tools`
- health, latency, discovered tools/models และ audit metadata

ขณะนี้ runtime adapter ที่ทำงานจริงคือ:

- `local`: Open WebUI `/api/models` และ `/api/chat/completions`
- `mcp`: MCP session + `call_tool`

`openai` ใช้ Responses API และเข้าร่วม health-aware failover ได้จริง ส่วน `claude`
ยังเป็น config placeholder และจะไม่ถูกเรียกจนกว่าจะมี adapter

OpenAI provider ใช้:

- `POST /v1/responses` สำหรับ advisory analysis
- `GET /v1/models/{model}` สำหรับ connection/model health check
- optional hosted `web_search`
- `store=false`
- exact host allowlist + HTTPS
- environment reference เช่น `ANALYSIS_PROVIDER_OPENAI_KEY`

## Local LLM

ใช้ Ollama เป็น inference engine และ Open WebUI เป็น gateway/UI:

| Memory | Model เริ่มต้น | ขนาดไฟล์โดยประมาณ |
|---|---|---:|
| 8 GB | `qwen3.5:4b` | 3.4 GB |
| 16 GB | `qwen3.5:9b` | 6.6 GB |
| 32 GB+ | `qwen3.5:27b` | 17 GB |

หน้า `Settings > Analysis Providers` ใช้เปิด/ปิด provider ได้ตลอด โดยไม่ต้องแก้โค้ด
ส่วน `WORKFLOW_ANALYSIS_ENABLED=false` เป็นค่าเริ่มต้นเพื่อไม่ให้ scheduler เรียก LLM
จนกว่าผู้ใช้จะเปิดเอง

Provider ที่ enabled จะถูกตรวจสุขภาพอัตโนมัติเมื่อ workflow scheduler ทำงาน โดยตั้งค่าได้ผ่าน:

- `ANALYSIS_PROVIDER_HEALTH_CHECKS_ENABLED`
- `ANALYSIS_PROVIDER_HEALTH_CHECK_INTERVAL_SECONDS`
- `ANALYSIS_PROVIDER_HEALTH_CHECK_BATCH_SIZE`

หน้า Settings มีปุ่มตรวจ provider ที่ enabled ทั้งหมดทันที การตรวจ provider ใดล้มเหลว
จะเปลี่ยน provider นั้นเป็น `UNHEALTHY` แต่ไม่ทำให้ workflow หรือ order path ล้ม

## Realtime Market Data

หน้า `Settings > Market Data` รองรับ:

- `mt5`: quote read-only จาก configured MT5 bridge
- `alpaca`: quote WebSocket สำหรับหุ้น พร้อม feed `iex`, `sip`, `delayed_sip`
- `disabled`: ปิด watchlist feed

ค่าที่ปรับได้:

- enabled/provider/endpoint/feed
- API key และ secret ผ่าน environment reference
- default symbols
- max symbols ต่อ connection
- timeout

สถานะ feed แสดงใน UI:

- `broker-realtime`
- `realtime-single-exchange`
- `realtime-consolidated`
- `delayed-consolidated`

ข้อสำคัญ: Alpaca ใช้สำหรับ watchlist/analysis เท่านั้น ราคา risk และ execution
ยังคงมาจาก MT5 เพื่อป้องกัน feed mismatch

## สิ่งที่ยังต้องตั้งค่าจริง

ฟังก์ชันต่อไปนี้ทำเป็น config แล้ว แต่ต้องมี service/credential ภายนอก:

1. Open WebUI/Ollama process และ Open WebUI API key
2. Alpaca API key/secret และ entitlement ของ feed ที่เลือก
3. MCP server จริง พร้อม tool contract `{query, context}`
4. Real news/calendar และ volatility data source
5. OpenAI/Claude adapters หากต้องการ cloud failover

## Definition of Done

### เสร็จแล้ว

- [x] Runtime analysis chokepoint
- [x] Local Open WebUI invocation
- [x] MCP tool invocation with allowlist
- [x] Capability routing and failover
- [x] Response size validation
- [x] Per-attempt provenance
- [x] Proposal explanation integration
- [x] Loss-review AI draft
- [x] Optional workflow analysis
- [x] AI Analysis page
- [x] MT5/Alpaca watchlist configuration and runtime
- [x] Credential values absent from DB/API/audit/snapshot
- [x] Periodic and manual batch provider health checks
- [x] OpenAI Responses API adapter with optional web search

### ยังเหลือ

- [ ] Live validation กับ Open WebUI/Ollama ของผู้ใช้
- [ ] Live validation กับ Alpaca account และ feed entitlement ของผู้ใช้
- [ ] Real news/calendar adapter
- [ ] Real volatility/session adapter
- [ ] Live OpenAI account/model validation
- [ ] Claude adapter
- [ ] Production metrics and alert delivery

## References

- [Open WebUI API endpoints](https://docs.openwebui.com/reference/api-endpoints/)
- [Model Context Protocol documentation](https://modelcontextprotocol.io/docs/getting-started/intro)
- [Alpaca realtime market-data WebSocket](https://docs.alpaca.markets/docs/streaming-market-data)
- [Qwen 3.5 model tags](https://ollama.com/library/qwen3.5/tags)
