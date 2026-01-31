# Runbook: deploy, recover, operate

## Deploy

1. Clone repo; copy `.env.example` to `.env` and set all required vars.
2. Run schema: `psql "$DATABASE_URL" -f src/app/db/schema.sql` (or use scripts/run_schema.py with asyncpg).
3. Build and run: `docker-compose up -d`.
4. Set Telegram webhook (HTTPS required):
   ```bash
   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     -d "url=https://your-domain.com/webhook/telegram" \
     -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
   ```
5. Verify: `GET https://your-domain.com/health` returns 200.

## Rotate keys

- **Telegram**: Revoke old token in BotFather; set new `TELEGRAM_BOT_TOKEN`; restart app; re-set webhook.
- **Database**: Change Postgres password; update `DATABASE_URL`; restart app.
- **Sheets**: Update service account key path or JSON; set `GOOGLE_APPLICATION_CREDENTIALS`; restart.
- **Cron secret**: Set new `EOD_CRON_SECRET`; restart app; update cron job to send new `X-Cron-Secret` header.

## Recover DB

Restore from backup into a new Postgres instance; point `DATABASE_URL` to it; restart app.

## Cron jobs

- **Daily signal**: Call `POST /internal/run-daily-signal` with header `X-Cron-Secret: <EOD_CRON_SECRET>`. Run once per day (e.g. 12:00 UTC or 07:00 EST). Idempotent: if today's signal already exists, re-sends it to all allowed users; otherwise generates and sends.
- **EOD outcomes**: Call `POST /internal/run-eod-outcomes` with header `X-Cron-Secret: <EOD_CRON_SECRET>`. Run after 00:00 UTC (e.g. 00:30 UTC). Resolves WIN/LOSS for runs whose market has ended.
- **Sheets sync** (optional): If using Google Sheets, run sync every 5 min (e.g. worker script or cron calling a sync endpoint if you add one).
- **Admin heartbeat** (optional): Call `POST /internal/admin-heartbeat` with `X-Cron-Secret` to send a short status message to `ADMIN_CHAT_ID` (e.g. "Last signal at X, direction Y"). Run daily after the signal job.

## Replay missed jobs

- **Signal**: Run `/signal` manually in Telegram for the missed day, or call `POST /internal/run-daily-signal` (generates and sends to all users).
- **Outcome**: Call `outcomes.recorder.record_run_outcome(run_id, "WIN"|"LOSS"|"SKIP")` after resolving market (e.g. from resolution source).

## API outages

- **Polymarket down**: Signal may show "No active BTC daily market" or use cached data; no crash.
- **Data fetchers down**: Signal runs with partial data; missing sources flagged in reasoning.
- **DB down**: App starts; `/health` returns 503; signals not persisted; Telegram still works for commands that don’t need DB.

## Monitoring

- **Uptime**: Check `GET /health` every 5 min (e.g. UptimeRobot). Alert on 503 or timeout.
- **Admin alerts**: Set `ADMIN_CHAT_ID`; critical webhook errors are sent there.
