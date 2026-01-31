# Phase 9 — Production deployment

## Purpose

Run the bot in a stable, observable way: Dockerized deploy, HTTPS termination, monitoring and alerting, runbook validation.

## Attach in Cursor

- This file
- `docs/context/runbook.md`
- `docs/context/observability.md`
- `docs/context/security.md`
- All prior phase code

## Files to create/modify

- `docker/Dockerfile` — multi-stage if desired; Python 3.11+, install deps, copy src, run uvicorn; non-root user
- `docker-compose.yml` — services: app (build from Dockerfile, env_file, depends_on db), db (Postgres 15+, volume for data); optional: nginx for HTTPS or use platform TLS
- `.env.example` — all required env vars with dummy values and comments (TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, TELEGRAM_ALLOWED_USER_IDS, DATABASE_URL, ADMIN_CHAT_ID, POLYMARKET_*, etc.)
- `docs/runbook.md` — copy/expand from context/runbook.md: deploy steps, rotate keys, recover DB, replay jobs, API outages, monitoring
- Monitoring: ensure GET /health is exposed; document UptimeRobot or equivalent (check every 5 min, alert on 503 or timeout); document that CRITICAL errors already send to ADMIN_CHAT_ID
- Optional: `scripts/set_webhook.sh` — curl to Telegram setWebhook with URL and secret_token
- README: add "Production" section: build, run with docker-compose, set env, set webhook, verify /health

## Acceptance criteria

- `docker-compose up` brings up app and Postgres; app connects to DB and responds on /health
- HTTPS in front of app (reverse proxy or platform); webhook URL is https://
- Runbook documents: deploy, key rotation, DB restore, replay missed signal/EOD job, what to do on API outage
- Monitoring: health check every 5 min; alert if down; admin already gets critical errors via Telegram
- No secrets in image or runbook; all from env

## Testing checklist

- Build image and run docker-compose locally; hit /health; send test webhook (with secret)
- Verify runbook steps (at least deploy and set webhook) on a staging or prod-like environment
- README production section is complete and accurate

## Do not do

- Do not commit .env or secrets into repo
- Do not skip HTTPS for webhook (Telegram requires it)
- Do not assume single-host only; runbook should work for any host (e.g. cloud VM or PaaS)
