# Paper trading

## Enable paper mode

Set `PAPER_TRADING=true` in env. Every signal message will be prefixed with:

`[PAPER] Do not trade with real money.`

## Duration

Run paper mode for at least **14–30 days** before using real capital. Use `/stats` and calibration to validate.

## Order book snapshot (paper mode)

When `PAPER_TRADING=true`, each signal run stores an order book snapshot (top levels, timestamp) in `signal_runs.order_book_snapshot`. This enables slippage audits without re-fetching the book.

**Migration:** If the column is missing, run:
```bash
psql "$DATABASE_URL" -f scripts/migrate_add_order_book_snapshot.sql
```

## Slippage audit

In paper mode you can compare the quoted market price to the volume-weighted average price (VWAP) for the recommended size:

- Use `app.analytics.slippage_audit.vwap_for_size_usd(book, "ask", size_usd)` with the order book snapshot at signal time.
- Compare to quoted best ask; `slippage_bps(quoted, vwap)` gives basis points.

**Slippage report script:** Load last N paper runs with stored snapshots and output avg/95th percentile slippage (bps):

```bash
uv run python scripts/slippage_report.py --limit 20
```

Example output: `Runs: 15`, `Avg slippage: 12.3 bps`, `95th percentile: 25.0 bps`. Aim for e.g. "95% of signals had &lt;1% slippage" (100 bps) before going live.

## Weight tuning

1. Run paper mode and collect outcomes.
2. Review calibration (predicted vs actual win rate by bucket) via `/stats`.
3. Adjust factor weights in `app.signal.weights.DEFAULT_WEIGHTS` or via config.
4. Re-run paper for another period before going live.
