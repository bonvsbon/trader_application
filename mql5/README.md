# ทางรอด MQL5 Bridge EA

`ThangRodBridgeEA.mq5` is the outbound TCP client for the backend server in
`backend/app/bridge/ea_socket_bridge.py`.

## Install

1. Open MetaEditor and copy `ThangRodBridgeEA.mq5` into `MQL5/Experts/`.
2. Compile the EA and attach it to one chart.
3. In MT5, open **Tools > Options > Expert Advisors** and allow the backend
   address, normally `127.0.0.1`.
4. Set backend `MT5_BRIDGE_TYPE=ea_socket` and a strong
   `MT5_EA_SHARED_SECRET`.
5. Set the EA `BackendSharedSecret` input to the same value.
6. Keep `AllowExecution=false` during connectivity/account/quote testing.
7. Enable `AllowExecution=true` only on a demo account after the full safety
   checklist passes. `AllowRealTrading` remains a separate opt-in guard.

Keep the backend bind address on loopback unless the connection uses a
protected tunnel. Remote binds require `MT5_EA_ALLOW_REMOTE_BIND=true`.

## Location On This Mac

- Source to open/compile in MetaEditor:
  `/Users/sittichaisuwatchareerak/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Experts/ThangRodBridgeEA.mq5`
- Compiled EA:
  `/Users/sittichaisuwatchareerak/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Experts/ThangRodBridgeEA.ex5`
- Repository source of truth:
  `/Users/sittichaisuwatchareerak/Project/trader_application/mql5/ThangRodBridgeEA.mq5`

MetaEditor build 5836 compiled the current source on 2026-06-13 with
`0 errors, 0 warnings`.

`PollIntervalMs` defaults to 100 ms. On the local demo setup this reduced a
42-candle request from about 5.2 seconds to 0.1 seconds and the dashboard
aggregate from about 27.2 seconds to 0.6 seconds.

## Current Limitations

- EA idempotency results are persisted per MT5 login in the terminal Common
  Files area. `IdempotencyCacheMax` bounds the cache; no credentials are stored.
- Demo login `10011170709` passed authenticated read and reconnect soak on
  2026-06-13 with `AllowExecution=false` and `AllowRealTrading=false`.
- A longer execution, timeout, and uncertain-order reconciliation soak remains.
- Real-account operation is not approved; use demo only.
