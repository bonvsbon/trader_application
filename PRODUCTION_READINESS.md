# Production Readiness Checklist

Real-money trading remains blocked until every required item is complete.

## Safety

- [x] Free official-US economic calendar is healthy and stale/failure tested.
- [ ] Live volatility/session provider is healthy during market hours.
      MT5 stale-data/weekend fail-closed behavior is tested.
- [ ] D40/D20 signal semantics are approved and covered by deterministic tests.
- [ ] Emergency stop is tested from UI and environment configuration.
- [ ] Daily loss, cooldown, portfolio risk, and spread limits are demo-verified.
- [ ] Manual approval expiry and concurrent approval tests pass.

## MT5

- [x] EA compiles without warnings in MetaEditor.
- [x] Shared-secret authentication rejects invalid clients.
- [x] Expected login, server, and DEMO account type match.
- [x] Disconnect and listener restart/reconnect read soak tests pass.
- [ ] Timeout and uncertain-order reconciliation soak tests pass.
- [ ] Deal/order/position ticket mapping is verified against the broker.
- [ ] `AllowRealTrading` remains disabled in the EA until final approval.

## Security

- [ ] API and EA secrets come from a secret manager, not source control.
- [ ] TLS or a private VPN protects all remote traffic.
- [ ] Firewall limits web and EA access to trusted sources.
- [ ] Operator roles, session expiry, and audit identity are deployed.
- [ ] Dependency and container vulnerability scans pass.

## Operations

- [ ] PostgreSQL backups run automatically and a restore drill has passed.
- [ ] Metrics and alerts cover bridge health, workflow failures, blocked orders,
      reconciliation age, database health, and disk usage.
- [ ] Log retention and incident response ownership are defined.
- [ ] Deployment rollback has been rehearsed.
- [ ] Demo soak period and acceptance criteria are complete.
      Auto-demo is implemented but remains disabled pending live provider gates.
