# Operations

## Docker deployment

1. Copy `.env.example` to `.env`.
2. Set unique URL-safe values for `POSTGRES_PASSWORD`, `API_AUTH_TOKEN`, and,
   when using the EA bridge, `MT5_EA_SHARED_SECRET`.
3. Keep `ALLOW_REAL_TRADING=false`, `ALLOW_AUTO_REAL_FULL=false`, and
   `EMERGENCY_STOP=true` for the first deployment.
4. Run `docker compose config` and review the resolved configuration.
5. Run `docker compose up --build -d`.
6. Open `http://127.0.0.1:8080` and verify Dashboard, Risk Monitor, Logs, and
   MT5 Account before enabling any execution.

The Compose ports bind to loopback. Put a TLS reverse proxy or private VPN in
front of the web app for remote access. Do not expose PostgreSQL publicly.
The default Compose deployment also forces `EMERGENCY_STOP=true`.

## MT5 EA

The EA normally connects to `127.0.0.1:5555` on the Docker host. For the
container listener, set `MT5_EA_HOST=0.0.0.0` and
`MT5_EA_ALLOW_REMOTE_BIND=true`; the Compose port itself remains bound to host
loopback. Set
`BackendSharedSecret` in the EA to the same value as
`MT5_EA_SHARED_SECRET`. Keep `AllowExecution=false` until demo connectivity,
account allowlist, quote, position, history, and reconciliation tests pass.

If MT5 runs on another host, use a protected tunnel. Set
`MT5_EA_ALLOW_REMOTE_BIND=true` only after restricting firewall source
addresses; the socket protocol does not provide TLS.

## Database backup

Create an encrypted backup outside the container volume:

```bash
docker compose exec -T database pg_dump -U trader -d trader -Fc > trader.dump
```

Test restore into a separate database:

```bash
docker compose exec -T database createdb -U trader trader_restore
docker compose exec -T database pg_restore -U trader -d trader_restore --clean --if-exists < trader.dump
```

Schedule backups, define retention, and perform a restore drill before
real-money approval.

## Upgrade and rollback

1. Back up PostgreSQL.
2. Build and run tests for the new version.
3. Run `docker compose up --build -d`; backend startup applies Alembic migrations.
4. Verify `/health`, account configuration, risk status, and a demo-only order.
5. For rollback, restore the prior application image. If a migration is not
   backward compatible, restore the pre-upgrade database backup.
