# Runbook: deploy, recover, operate

## Deploy

- Build and run via Docker Compose (app + Postgres). Use env file for secrets. HTTPS termination at reverse proxy (e.g. Nginx) or platform (e.g. Cloud Run). Set webhook URL to `https://your-domain/webhook/telegram` with secret token.
- **Production:** Set `EOD_CRON_SECRET` in env. The EOD endpoint returns 403 when the secret is unset; cron jobs must send the `X-Cron-Secret` header.

## Rotate keys

- **Telegram**: Revoke old token in BotFather, set new token in env, restart. Re-register webhook with new secret if changed.
- **Database**: Change password in Postgres, update `DATABASE_URL`, restart app.
- **Polymarket / Google**: Update env vars and restart.

## Recover DB

- Restore from latest backup (document backup schedule). Point app to restored DB. Replay any missed jobs if needed (see below).

## Replay missed jobs

- If the app was down at signal time: run signal job manually (e.g. script or admin command) for the missed date with stored or re-fetched data. Log as "manual_replay."
- Outcome job: run EOD job for a specific date to backfill outcome (WIN/LOSS/SKIP) from resolution source.

## API outages

- If Polymarket is down: skip signal or cache last order book and warn "Market data stale." If data fetchers are down: generate signal with partial data and flag; do not crash.

## Monitoring

- Uptime check on `/health` every 5 min. Alert if 503 or timeout. On failure, check logs and DB connectivity first.

## Migrations and schema

- Run schema and migration scripts **before** deploying app code that depends on them. Order: apply new SQL (e.g. `scripts/run_schema.py`, any `scripts/migrate_*.sql`), then deploy. Optional: add a follow-up migration to set `signal_runs.market_condition_id` NOT NULL after all runs have it set (Phase 2 inserts it at create time).

## Circuit breaker

- Fetcher circuit breaker state is **per process** (in-memory). With multiple app instances, each has its own state; one instance may keep calling a failing API while another has the circuit open. For consistent behavior across instances, run a single instance or introduce a shared store (e.g. Redis) later.
