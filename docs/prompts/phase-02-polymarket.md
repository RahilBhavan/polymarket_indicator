# Phase 2 — Polymarket integration

## Purpose

Reliably read the active BTC daily market, best bid/ask, spread, implied probability, and order book depth to compute max safe size (slippage cap). Store market metadata including resolution source for later outcome recording.

## Attach in Cursor

- This file
- `docs/context/polymarket-spec.md`
- `docs/context/domain.md`
- Phase 1 code: `src/app/main.py`, `src/app/config.py`, `src/app/db/`

## Files to create/modify

- `src/app/polymarket/client.py` — async client for Gamma API (markets list, filter BTC daily) and CLOB API (order book by condition_id or market)
- `src/app/polymarket/models.py` — Pydantic models: Market, OrderBook, Level, MarketQuote (best_bid, best_ask, spread, implied_prob_yes)
- `src/app/polymarket/selection.py` — select active daily BTC market for date (or "today")
- `src/app/polymarket/depth.py` — compute max_safe_size_usd given order book and SLIPPAGE_LIMIT (e.g. 1%)
- DB: store market_metadata (condition_id, slug, resolution_source, end_date_utc) per run or in a small table
- `src/app/telegram/handler.py` — add /signal stub that calls polymarket client and returns diagnostic: market, best bid/ask, spread, implied prob, depth at levels

## Acceptance criteria

- Given a date, selection returns one active BTC daily market (or clear "none found")
- Order book returns best bid, best ask, spread, and list of levels (price, size)
- implied_prob_yes = best_ask (for binary YES)
- max_safe_size_usd computed so that volume-weighted slippage <= SLIPPAGE_LIMIT
- Resolution source (e.g. "Binance BTC/USDT 23:59 UTC") parsed and stored
- /signal (stub) sends a message with: market slug, best bid/ask, spread, implied %, max safe size

## Testing checklist

- Unit test: order book parsing from CLOB response
- Unit test: max_safe_size_usd for a synthetic book
- Integration test (or manual): Gamma + CLOB return valid data for a known BTC daily market; no crash
- Test with mock responses if APIs require keys

## Do not do

- Do not implement signal engine (Model_P, Edge) yet
- Do not commit API keys; use env and .env.example
