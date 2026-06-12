# Local AI and Realtime Market Data Setup

แอป **ทางรอด** ใช้ Open WebUI เป็น local AI gateway, Ollama เป็น inference engine
และรองรับ Alpaca เป็น external realtime stock watchlist แบบ read-only

AI และ external market data ไม่มีสิทธิ์ส่ง order โดยตรง

## 1. เลือก Local Model

| Memory | Model แนะนำ | ขนาดไฟล์โดยประมาณ |
|---|---|---:|
| 8 GB | `qwen3.5:4b` | 3.4 GB |
| 16 GB | `qwen3.5:9b` | 6.6 GB |
| 32 GB+ | `qwen3.5:27b` | 17 GB |

สำหรับ Mac M1 หรือ Windows RAM 16 GB ให้เริ่มที่ `qwen3.5:9b`

```powershell
ollama pull qwen3.5:9b
ollama list
```

## 2. รัน Open WebUI

ตัวอย่าง Docker:

```powershell
docker run -d `
  -p 127.0.0.1:3000:8080 `
  --add-host=host.docker.internal:host-gateway `
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 `
  -v open-webui:/app/backend/data `
  --name open-webui `
  --restart unless-stopped `
  ghcr.io/open-webui/open-webui:main
```

ก่อน production ควร pin image เป็น release ที่ทดสอบแล้วแทน tag `main`

เปิด `http://127.0.0.1:3000`, สร้าง local admin และ Open WebUI API key

## 3. ตั้งค่า Open WebUI Secret

เพิ่มใน `.env`:

```dotenv
ANALYSIS_PROVIDER_OPEN_WEBUI_KEY=<open-webui-api-key>
ANALYSIS_PROVIDER_ALLOWED_HOSTS=localhost,127.0.0.1,::1
WORKFLOW_ANALYSIS_ENABLED=false
```

จากนั้น restart backend และเปิด `Settings > Analysis Providers`:

- Provider type: `LOCAL`
- Endpoint: `http://127.0.0.1:3000`
- Model: model ที่ pull ไว้
- Secret reference: `ANALYSIS_PROVIDER_OPEN_WEBUI_KEY`
- Enabled: เปิด/ปิดได้ตลอด
- Web search: เปิดเมื่อ Open WebUI ตั้ง search provider แล้ว
- Capabilities: เลือกงานที่ provider นี้รับผิดชอบ

กด `Save provider` และ `Test connection` จนสถานะเป็น `HEALTHY`

ทดสอบเรียกจริงได้ที่เมนู `AI Analysis`

## 4. ตั้งค่า MCP Provider

ที่ `Settings > Analysis Providers`:

1. เลือก provider type `MCP`
2. ระบุ HTTPS หรือ localhost endpoint
3. เลือก transport
4. กด test/discover tools
5. เลือก `allowed_tools`
6. map capability แต่ละรายการไปยัง tool ที่อนุญาต
7. เปิด Enabled และบันทึก

Runtime ส่ง arguments รูปแบบ:

```json
{
  "query": "analysis prompt",
  "context": {}
}
```

## 5. ตั้งค่า Realtime Stock Feed

เพิ่ม Alpaca credential ใน `.env`:

```dotenv
MARKET_DATA_ALPACA_KEY=<alpaca-api-key>
MARKET_DATA_ALPACA_SECRET=<alpaca-api-secret>
MARKET_DATA_ALLOWED_HOSTS=stream.data.alpaca.markets
```

เปิด `Settings > Market Data`:

- Provider: `Alpaca`
- Endpoint: `wss://stream.data.alpaca.markets`
- Feed:
  - `iex`: realtime จาก IEX
  - `sip`: consolidated realtime และอาจต้องมี subscription
  - `delayed_sip`: consolidated delayed
- API key reference: `MARKET_DATA_ALPACA_KEY`
- API secret reference: `MARKET_DATA_ALPACA_SECRET`
- Default symbols: เช่น `AAPL`, `MSFT`, `NVDA`

กด `Save` แล้ว `Test connection`

Dashboard จะแสดง source และ feed status ชัดเจน ราคา Alpaca ใช้สำหรับ watchlist
และ analysis เท่านั้น ส่วน risk/execution ยังใช้ MT5

## 6. Environment Defaults

ค่าทั้งหมดมี default ใน `.env.example` และแก้ผ่าน UI ได้ โดย DB เก็บเฉพาะ config
กับชื่อ environment variable ไม่เก็บ secret value

ตั้งค่าการตรวจสุขภาพอัตโนมัติ:

```dotenv
ANALYSIS_PROVIDER_HEALTH_CHECKS_ENABLED=true
ANALYSIS_PROVIDER_HEALTH_CHECK_INTERVAL_SECONDS=300
ANALYSIS_PROVIDER_HEALTH_CHECK_BATCH_SIZE=10
```

การตรวจอัตโนมัติทำงานเมื่อ workflow scheduler เปิดอยู่ และจะตรวจเฉพาะ provider
ที่ enabled และครบกำหนดเวลาแล้ว หน้า `Settings > Analysis Providers` มีปุ่ม
`Check enabled providers` สำหรับตรวจทันที

## 7. Optional OpenAI Fallback

เพิ่ม key ใน `.env`:

```dotenv
ANALYSIS_PROVIDER_OPENAI_KEY=<openai-api-key>
OPENAI_PROVIDER_ALLOWED_HOSTS=api.openai.com
```

สร้าง provider ที่ `Settings > Analysis Providers`:

- Provider type: `OPENAI`
- Endpoint: `https://api.openai.com/v1`
- Model: เลือก model ที่บัญชีมีสิทธิ์ใช้งาน
- Secret reference: `ANALYSIS_PROVIDER_OPENAI_KEY`
- Enabled: ปิดไว้ก่อน แล้วเปิดเมื่อพร้อมทดสอบ
- Web search: optional และอาจมี usage เพิ่ม
- Priority: เลขมากกว่า local provider หากต้องการใช้เป็น fallback

กด `Test connection` ก่อน provider จะเข้า capability route แอปส่ง Responses API
request แบบ advisory และกำหนด `store=false`

## References

- [Open WebUI API endpoints](https://docs.openwebui.com/reference/api-endpoints/)
- [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling)
- [Qwen 3.5 model tags](https://ollama.com/library/qwen3.5/tags)
- [MCP documentation](https://modelcontextprotocol.io/docs/getting-started/intro)
- [Alpaca streaming market data](https://docs.alpaca.markets/docs/streaming-market-data)
- [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [OpenAI model retrieval](https://developers.openai.com/api/reference/resources/models/methods/retrieve)
