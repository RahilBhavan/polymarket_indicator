# Telegram message specification

## Summary signal message (default)

- **Title**: e.g. "SIGNAL: BTC Daily (YYYY-MM-DD)"
- **Direction**: YES / NO / NO TRADE
- **Model confidence**: Model_P as percentage (e.g. 72%)
- **Market price**: Best ask (for YES) in cents, e.g. "61c (implied 61%)"
- **Edge**: e.g. "+11%"
- **Recommended bet**: e.g. "2.5% of bankroll (Kelly 0.25x)" and/or "$X"
- **Reasoning**: One line or two (strongest factors).
- **Liquidity warning** (if applicable): "Wide spread" or "Max bet $200 before slippage > 1%"
- **Generated**: Timestamp (e.g. 7:00 AM EST)

Max length per message: 4096 characters (Telegram limit). Split into follow-up messages if needed.

## Verbose / full details

- All of the above plus:
- **Factor breakdown**: Each factor name, raw value, score contribution, stale/missing flag.
- **Order book**: Best bid, best ask, spread, depth at 1% intervals (optional, can be second message).

## Inline keyboard actions

- **Full Details** – toggle or send verbose breakdown.
- **Open Polymarket** – deep link to the market page.
- **Settings** – open settings menu (Phase 6).

## Commands response types

- `/start`: Welcome + short description + link to /help.
- `/signal`: Today's signal (summary). If not yet generated, trigger or show "Not yet generated."
- `/status`: Bot health, DB connected, last signal time, data source status (ok/stale/fail).
- `/history [n]`: Last n signals with outcome (WIN/LOSS/SKIP).
- `/stats`: Win rate, calibration, drawdown, recent streak.
- `/settings`: Inline menu for threshold, bankroll, verbosity.
- `/help`: List of commands and usage.

## Rate limiting

- Max 30 messages per second to Telegram. Use token bucket or simple throttle when sending to multiple users or long history.
