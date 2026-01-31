# Phase 8 — Paper trading

## Purpose

Validate the bot forward: run in "paper" mode (all signals sent but clearly tagged "PAPER"); compare quoted price vs achievable price (slippage audit using order book snapshots); run for at least 14–30 days; tune weights if needed.

## Attach in Cursor

- This file
- `docs/context/signal-spec.md`
- `docs/context/polymarket-spec.md`
- Phase 4 engine, Phase 5 outcomes/analytics

## Files to create/modify

- `src/app/config.py` — PAPER_TRADING = true/false; when true, every signal message includes a clear tag e.g. "[PAPER] Do not trade with real money."
- `src/app/signal/engine.py` — in paper mode, still compute and store everything; optional: store order_book_snapshot (best bid/ask, levels) at signal time for later slippage audit
- `src/app/analytics/slippage_audit.py` — given a signal run and stored order book snapshot, compute "if we had placed a market order for recommended_usd, what would VWAP have been?"; compare to quoted market price; report avg slippage bps
- `src/app/telegram/formatter.py` — when PAPER_TRADING, prepend or append paper disclaimer to signal message
- `docs/paper_trading.md` — how to run paper mode, how long to run (14–30 days), how to read slippage audit, how to tune weights (change weights in config, re-run backtest if available, then another paper period)
- Optional: small script or /admin command to generate slippage report for last N paper signals

## Acceptance criteria

- Paper mode clearly indicated in every signal message; no ambiguity that it is not live
- Order book snapshot at signal time stored when in paper mode (if implemented)
- Slippage audit script/report produces avg slippage and distribution (e.g. "95% of signals had <1% slippage")
- Documentation describes minimum paper period and weight-tuning workflow

## Testing checklist

- Unit test: slippage calculation from synthetic order book and size
- Manual: run bot in paper mode for 1 day; confirm tag appears; confirm outcomes still recorded
- Optional: run slippage audit on 10 stored paper runs

## Do not do

- Do not allow "live" tagging while PAPER_TRADING=true
- Do not skip outcome recording in paper mode; we need calibration and slippage data
- Do not ship to real money before at least 14 days paper and acceptable calibration/slippage
