# Phase 1 — Foundation

## Purpose

Build a runnable skeleton: FastAPI app, Telegram webhook handler with user whitelist, Postgres schema and migrations, config from env, `/status` command, and structured logging. No signal logic yet.

## Attach in Cursor

- This file
- `docs/context/security.md`
- `docs/context/observability.md`

## Files to create/modify

- `src/app/main.py` — FastAPI app, webhook route, health route
- `src/app/config.py` — Pydantic settings from env (DATABASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, TELEGRAM_ALLOWED_USER_IDS)
- `src/app/db/schema.sql` or Alembic migration — tables: users (id, telegram_user_id, created_at), signal_runs (id, run_at, status, ...), app_config (key, value) if needed
- `src/app/db/session.py` — async Postgres connection (asyncpg or SQLAlchemy async)
- `src/app/telegram/handler.py` — parse Update, whitelist check, dispatch /start, /status, /help; respond with text
- `src/app/telegram/webhook.py` — verify X-Telegram-Bot-Api-Secret-Token, forward to handler
- `src/app/logging.py` — structlog or JSON logger
- `pyproject.toml` or `requirements.txt` — FastAPI, uvicorn, asyncpg (or sqlalchemy[asyncio]), pydantic-settings, python-telegram-bot or httpx for sendMessage
- `.env.example` — list required env vars (no secrets)
- `README.md` — how to run (uv run / pip install, set env, run uvicorn)

## Acceptance criteria

- `GET /health` returns 200 with {"status":"ok","db":"connected"} when DB is up; 503 when DB is down
- POST to webhook with valid secret token and allowed user: /start and /status produce replies
- POST without valid secret token: 403
- Command from non-whitelisted user: ignored or "Unauthorized"
- All secrets from env; no hardcoded tokens
- Structured logs for incoming request and command

## Testing checklist

- Unit test: config loads from env and validates
- Integration test: /health returns 200 with DB up
- Integration test: webhook returns 403 when secret header missing or wrong
- Integration test: /start and /status return 200 and send Telegram message (mock or test bot)

## Do not do

- Do not implement signal generation or data fetchers
- Do not store Telegram token in code or logs
- Do not skip whitelist check for any command
