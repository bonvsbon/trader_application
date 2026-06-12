# MT5 Bridge Skill

Operational notes for the MT5 bridge:

- Python is the TCP server; the MQL5 EA connects outward as a client.
- MT5 passwords stay inside MT5 Terminal. The app stores only the expected
  login/server/account type and blocks trading on mismatch.
- Changing runtime MT5 config stops the workflow and replaces the bridge.
- EA idempotency results persist per MT5 login in Common Files and are bounded
  by `IdempotencyCacheMax`.
- See `backend/app/bridge/protocol.md` for the wire protocol and retcodes.
- MetaEditor compilation and demo soak testing are still required.
