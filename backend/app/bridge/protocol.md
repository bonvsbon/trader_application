# EA Socket Bridge — Protocol

Transport: **TCP**, newline-delimited **JSON** (one JSON object per line, UTF-8).
The Python backend (`ea_socket_bridge.py`) is the **server**; the MQL5 Expert
Advisor connects outward as the **client**. Native MQL5 exposes `SocketConnect`
but does not expose TCP listen/accept APIs.

Default backend listening endpoint: `MT5_EA_HOST:MT5_EA_PORT`
(e.g. `127.0.0.1:5555`).

## Authentication handshake

Immediately after connecting and before any RPC traffic, the EA must send:

```json
{ "type": "auth", "secret": "<MT5_EA_SHARED_SECRET>" }
```

The backend rejects missing or incorrect secrets. Non-loopback bind addresses
also require `MT5_EA_ALLOW_REMOTE_BIND=true`.

## Request

```json
{ "id": "<request-id>", "method": "<name>", "params": { ... } }
```

## Response

```json
{ "id": "<request-id>", "result": { ... } }          // success
{ "id": "<request-id>", "error": "human-readable" }  // failure
```

## Methods

| Method | Params | Result |
|--------|--------|--------|
| `health` | – | `{ "ok": true, "detail": "...", "server_time_epoch": 1781164800 }` |
| `account_info` | – | `{ "account_type": "DEMO\|REAL", "login": 123, "server": "...", "currency": "USD", "balance": 0, "equity": 0, "margin": 0, "free_margin": 0, "leverage": 100 }` |
| `quote` | `{ "symbol": "XAUUSD" }` | `{ "bid": 2349.8, "ask": 2350.2, "spread_points": 40, "time_epoch": 1781164800 }` |
| `symbol_info` | `{ "symbol": "XAUUSD" }` | `{ "tick_size": 0.01, "tick_value": 1.0, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01 }` |
| `candles` | `{ "symbol": "XAUUSD", "timeframe": "H1", "count": 42 }` | `{ "candles": [ { "time_epoch": 1781164800, "open": 2350.0, "high": 2352.0, "low": 2349.0, "close": 2351.0, "volume": 1000 } ] }` — closed bars, oldest first; powers the D40/D20 Donchian signal |
| `positions` | – | `{ "positions": [ { "ticket": 1, "symbol": "XAUUSD", "side": "BUY", "volume": 0.1, "open_price": 2350.0, "sl": null, "tp": null, "profit": 0.0 } ] }` |
| `closed_trades_today` | – | `{ "trades": [ <closed-trade> ] }` |
| `closed_trades_range` | `{ "start_epoch": 1781000000, "end_epoch": 1781164800 }` | `{ "trades": [ <closed-trade> ] }` — for historical backfill |
| `order_status` | `{ "idempotency_key": "..." }` | `{ "found": true, "order": { "ticket": 123, "retcode": 10009, ... } }` or `{ "found": false }` |

A `<closed-trade>` object requires `ticket`, `symbol`, `profit`, and `close_time`
(ISO string or `close_time_epoch`). It MAY include journal fields the UI shows:
`side`, `volume`, `entry_price`, `exit_price`, `open_time`/`open_time_epoch`, and
`exit_reason` (`"tp" | "sl" | "manual" | "other"`).
| `execute_order` | `{ "symbol", "side", "volume", "sl", "tp", "idempotency_key" }` | `{ "ticket": 123, "retcode": 10009, "price": 2350.2, ... }` |

## Safety notes

- `execute_order` must return an integer MT5 `retcode`. The backend treats
  `10009` as filled, `10010` as partially filled, `10008` as accepted/pending,
  and other retcodes as broker rejection. A completed response must include a
  `ticket`; malformed responses require reconciliation and never become `FILLED`.
- `account_type` MUST be returned accurately; the backend blocks trading when it is `UNKNOWN`.
- The backend already enforces idempotency, but the EA **must** also dedupe by
  `idempotency_key` as a second line of defence against double orders. The
  supplied EA persists this cache per MT5 login across terminal restarts.
- If the EA is not connected, the backend reports `UNKNOWN` health and the Risk
  Engine blocks all trading. This is the intended
  fail-safe ("bridge not ready => block").
- The EA should refuse `execute_order` if its own kill switch / config disallows it.
