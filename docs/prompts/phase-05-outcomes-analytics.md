# Phase 5 — Outcome recording and analytics

## Purpose

Close the loop: end-of-day job records outcome (WIN/LOSS/SKIP) using the correct resolution source (e.g. Binance close for that market). Compute rolling win rate, calibration error (predicted vs realized), drawdown, and factor attribution. Expose via /stats and optional API.

## Attach in Cursor

- This file
- `docs/context/domain.md`
- `docs/context/polymarket-spec.md`
- Phase 2 (resolution source), Phase 4 (signal_runs table)

## Files to create/modify

- `src/app/outcomes/resolution.py` — for a given market, resolve outcome: fetch resolution source (e.g. Binance close at 23:59 UTC), compare to market rule (e.g. "above $96,500"), return YES or NO
- `src/app/outcomes/recorder.py` — EOD job: for each signal_run that has no outcome yet and whose market has ended, call resolution; set outcome WIN/LOSS/SKIP; update signal_runs.outcome, signal_runs.resolved_at
- `src/app/analytics/rolling.py` — rolling win rate (e.g. last 30), profit factor (gross profit / gross loss) if we have PnL, streak
- `src/app/analytics/calibration.py` — bucket by predicted confidence (e.g. 60–70%, 70–80%); actual win rate per bucket; calibration error = |predicted - actual|
- `src/app/analytics/drawdown.py` — peak-to-trough decline from cumulative PnL (or from win/loss sequence)
- `src/app/analytics/factor_attribution.py` — which factors correlated with WIN vs LOSS (optional, simple version: avg contribution of each factor on WIN vs LOSS)
- DB: signal_runs.outcome (WIN/LOSS/SKIP), signal_runs.resolved_at, signal_runs.actual_result (YES/NO if needed)
- `src/app/telegram/handler.py` — /stats returns: win rate (last 30), calibration summary, current streak, max drawdown, last N outcomes
- Scheduler: add EOD job (e.g. after 00:00 UTC next day) to run recorder

## Acceptance criteria

- Resolution uses the same source as market rules (e.g. Binance close); no mismatch (e.g. Coinbase vs Binance)
- Outcome correctly set WIN when prediction matched outcome, LOSS when not, SKIP when no trade or unresolved
- Rolling win rate and calibration computed from stored outcomes
- /stats shows: win rate, calibration error, streak, drawdown, last outcomes
- EOD job can be run manually or on schedule without duplicate updates

## Testing checklist

- Unit test: resolution logic for a known market rule and price (e.g. close 96,600 vs strike 96,500 → YES)
- Unit test: calibration buckets with synthetic outcomes
- Integration test: recorder updates signal_runs for a mock resolved market
- Test /stats with a few seeded outcomes

## Do not do

- Do not assume resolution source; always parse from market metadata
- Do not overwrite existing outcome with a new one (idempotent)
- Do not expose PII in /stats
