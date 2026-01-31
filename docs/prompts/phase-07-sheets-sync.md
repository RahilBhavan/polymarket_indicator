# Phase 7 — Google Sheets sync (optional)

## Purpose

Human-friendly reporting: batched export from Postgres to Google Sheets (Daily Signals, Performance Summary). Respect Sheets API quota (e.g. 60 writes/min); use retries and dead-letter queue for failures.

## Attach in Cursor

- This file
- `docs/context/runbook.md`
- Phase 1 DB, Phase 4 signal_runs, Phase 5 outcomes

## Files to create/modify

- `src/app/sheets/client.py` — authenticate with service account (env GOOGLE_APPLICATION_CREDENTIALS or JSON path); scope spreadsheets + drive; batchUpdate for multi-row writes
- `src/app/sheets/sync.py` — read from Postgres: recent signal_runs with outcomes; transform to rows (Date, Timestamp, Asset, Direction, Confidence, Score, factors..., Actual Outcome, Result, Notes); append or batchUpdate in chunks (e.g. 50 rows per request); run every 5 min or on "trade closed" event
- `src/app/sheets/templates.md` — document sheet structure: Sheet1 "Daily Signals" (columns A–P), Sheet2 "Performance Summary" (formulas or computed from Sheet1), Sheet3 "Config" (read-only reference)
- Config: SPREADSHEET_ID, SYNC_ENABLED, SYNC_INTERVAL_MINUTES; optional SYNC_DEAD_LETTER_QUEUE (e.g. table or file for failed batch IDs)
- Worker or background task: run sync in loop or triggered by scheduler; on 429, back off and retry; on persistent failure, write to dead-letter and alert

## Acceptance criteria

- New signal runs (and outcome updates) appear in Sheets within sync interval (e.g. 5 min)
- Batch writes used; no single-row-per-request for bulk; stay under 60 requests/min
- If Sheets API fails, retry with backoff; after N failures, log and optionally dead-letter; bot and signal generation continue without Sheets
- Sheet structure matches documented template; Performance Summary updates (formulas or periodic recompute)

## Testing checklist

- Unit test: row transformation from signal_run + snapshot to sheet row
- Integration test: mock Sheets API (or test spreadsheet); sync writes correct rows; 429 handling backs off
- Document in README: how to create spreadsheet, share with service account, set SPREADSHEET_ID

## Do not do

- Do not make Sheets the source of truth; Postgres remains authoritative
- Do not block signal generation or Telegram on Sheets availability
- Do not commit service account JSON; use env path only
