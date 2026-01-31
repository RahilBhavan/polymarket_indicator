# Observability: logs, health, alerts

## Structured logging

- Use structured fields (e.g. JSON or key=value): `timestamp`, `level`, `message`, `phase`, `signal_id`, `user_id`, `error_code`, `duration_ms`.
- Levels: DEBUG (dev only), INFO (signal generated, command received), WARNING (retry, stale data, circuit open), ERROR (failed op, exception), CRITICAL (system failure).
- Never log secrets or full request bodies containing tokens.

## Health endpoint

- `GET /health` or `GET /status`: returns 200 with payload `{"status":"ok","db":"connected","last_signal_at":...}`. Use for uptime checks. On DB or critical dependency failure return 503.

## Admin alerts

- On unhandled exception or CRITICAL: send a short message to a dedicated Telegram admin chat (e.g. `ADMIN_CHAT_ID`). Include: error type, timestamp, no stack trace in message (log full trace server-side).
- Optional: daily heartbeat to admin (e.g. "Bot ran, signal sent" or "No signal today").

## Retry and circuit breaker

- External API calls: retry with exponential backoff (e.g. 3 attempts, 1s / 2s / 4s). After N consecutive failures (e.g. 3), open circuit for T seconds (e.g. 300). Mark source as unavailable and log.
- Do not block signal generation: run with partial data and flag missing sources.
