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

## Current Limitations

- EA idempotency results are persisted per MT5 login in the terminal Common
  Files area. `IdempotencyCacheMax` bounds the cache; no credentials are stored.
- This file has not yet been compiled inside MetaEditor in this workspace.
- Real-account operation is not approved; use demo only.
