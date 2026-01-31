# Security requirements

## Webhook secret token

- When registering the Telegram webhook, set `secret_token` to a random string (e.g. 32 chars).
- Store in env as `TELEGRAM_WEBHOOK_SECRET`.
- On every incoming POST to the webhook URL: require header `X-Telegram-Bot-Api-Secret-Token` to equal that secret. If missing or wrong, return **403 Forbidden** and do not process.
- Ensures only Telegram servers can trigger the bot.

## User whitelist

- Only process commands from Telegram user IDs listed in `TELEGRAM_ALLOWED_USER_IDS` (comma-separated).
- Commands from other users: ignore silently or return "Unauthorized" (do not leak info).
- No blacklist-only mode for MVP.

## Secrets and env

- All secrets in environment variables: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `DATABASE_URL`, `POLYMARKET_*`, Google credentials path, etc.
- Never log tokens, API keys, or full credentials. Log only presence (e.g. "TELEGRAM_BOT_TOKEN is set") if needed for startup checks.
- `.env` and service-account JSON files must be in `.gitignore` and never committed.

## API keys rotation

- Document in runbook: rotate Telegram token and re-set webhook; rotate DB password; rotate any Polymarket/Google keys. Rotate quarterly or on compromise.
