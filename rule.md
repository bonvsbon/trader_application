Review the trading execution safety before modifying or adding order execution code.

Required safety behavior:

1. Real account auto trading must be disabled by default.
2. Real account order must require manual confirmation unless config explicitly enables AUTO_REAL_FULL.
3. AUTO_REAL_FULL must require multiple config flags, not just one boolean.
4. Unknown account type must block trading.
5. Unknown MT5 bridge status must block trading.
6. High-impact news must block trading.
7. Duplicate order suspicion must block trading.
8. Every order must have an idempotency key.
9. Every order must create an audit log.
10. Every order must store:

* strategy reason
* AI reason if available
* risk decision
* user approval if required
* MT5 response
* timestamp
* account type
* trading mode

Before coding, tell me exactly where these protections are implemented.
If any protection is missing, implement it before adding new trading features.
