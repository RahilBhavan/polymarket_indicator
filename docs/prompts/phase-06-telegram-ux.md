# Phase 6 — Telegram UX polish

## Purpose

Make the bot feel productized: full command suite (/signal, /history, /stats, /settings, /status, /help), inline buttons (Full Details, Open Polymarket, Settings), message splitting and rate limiting, and admin alerts for errors.

## Attach in Cursor

- This file
- `docs/context/message-spec.md`
- `docs/context/security.md`
- Phase 1, 4, 5 handlers and signal/analytics code

## Files to create/modify

- `src/app/telegram/handler.py` — implement all commands: /signal (trigger generation if not yet done, then send summary), /history [n], /stats, /settings (inline menu: threshold, bankroll, verbosity), /status, /help; callback_query for inline buttons (Full Details → send verbose message; Open Polymarket → send URL; Settings → settings menu)
- `src/app/telegram/formatter.py` — format signal message (summary and verbose) per message-spec; split into multiple messages if >4096 chars
- `src/app/telegram/rate_limit.py` — simple throttle (e.g. 1 send per 0.5s or token bucket) to stay under 30 msg/s
- `src/app/telegram/admin.py` — on unhandled exception or CRITICAL log, send short alert to ADMIN_CHAT_ID (env); include error type and timestamp
- Config: ADMIN_CHAT_ID, optional VERBOSE_DEFAULT
- User preferences: store in DB or config (min_confidence, bankroll_usd, verbose) for /settings; apply when formatting and sizing

## Acceptance criteria

- /help lists all commands with short description
- /history 10 returns last 10 signals with outcome (WIN/LOSS/SKIP)
- /stats shows win rate, calibration, streak, drawdown
- /settings opens inline menu; changing bankroll or threshold persists and is used in next signal
- Inline "Full Details" sends verbose factor breakdown; "Open Polymarket" sends market URL
- Messages longer than 4096 chars are split; no truncation without notice
- Admin receives alert on critical failure; no secrets in alert message
- Unauthorized users get no response or "Unauthorized"

## Testing checklist

- Unit test: formatter produces summary and verbose within length limits
- Unit test: rate limiter throttles when many sends requested
- Integration test: /settings callback updates stored config
- Manual: full command flow and inline buttons on real bot

## Do not do

- Do not send stack traces or secrets to admin chat
- Do not process callback_queries from non-whitelisted users
- Do not forget to answer callback_query (answer()) within a few seconds to avoid Telegram "loading" state
