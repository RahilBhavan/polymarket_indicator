# Phase 3 — Data fetchers

## Purpose

Implement async, resilient data ingestion for all signal factors: ETF flows, funding, DXY, Fear & Greed, price/MA, exchange netflow, optional Coinbase premium and stablecoin issuance. Use caching, retries, and circuit breaker. Normalize into a daily "feature snapshot" and store in Postgres.

## Attach in Cursor

- This file
- `docs/context/data-sources.md`
- `docs/context/observability.md`
- Phase 1–2 code: `src/app/db/`, `src/app/config.py`

## Files to create/modify

- `src/app/fetchers/base.py` — abstract base: fetch() -> RawValue, normalize() -> score, MAX_AGE, circuit breaker state (failure_count, open_until)
- `src/app/fetchers/etf_flows.py` — Farside or SoSoValue (or scrape), return daily net flow USD
- `src/app/fetchers/funding.py` — Coinglass or Binance Futures, return funding rate
- `src/app/fetchers/dxy.py` — Yahoo Finance or TradingView, 5d trend %
- `src/app/fetchers/fear_greed.py` — alternative.me, index 0–100
- `src/app/fetchers/price_ma.py` — Binance or CoinGecko, price and 50 MA, % deviation
- `src/app/fetchers/exchange_netflow.py` — CryptoQuant or Glassnode (or mock if no key), 7d netflow BTC
- `src/app/fetchers/macro.py` — ForexFactory or Investing.com calendar (or mock), FOMC/CPI within 48h flag
- `src/app/fetchers/registry.py` — register all fetchers, run all in parallel (asyncio.gather), aggregate into FeatureSnapshot (timestamp, source_id, raw_value, score, stale)
- `src/app/db/feature_snapshots.py` — insert snapshot rows (run_id, source_id, raw_value, normalized_score, stale)
- Config: add FETCHER_TIMEOUT, CIRCUIT_FAILURE_THRESHOLD, CIRCUIT_OPEN_SECONDS, CACHE_TTL where applicable

## Acceptance criteria

- Each fetcher returns a result or marked unavailable (no crash). Stale data marked with stale=True.
- Circuit breaker: after N consecutive failures, stop calling for T seconds; then try again.
- Retry: 3 attempts with exponential backoff for transient errors.
- Feature snapshot stored in Postgres with run_id, source_id, raw_value, normalized_score, stale.
- One "daily snapshot" can be produced in <30s with partial data; missing sources clearly flagged.

## Testing checklist

- Unit tests: each fetcher's normalize() with known inputs
- Unit test: circuit breaker opens after N failures and skips calls when open
- Integration test: run registry with mocks (respx/httpx) to avoid real API calls; snapshot shape correct
- Optional: one live test per source (skip in CI if no keys)

## Do not do

- Do not block signal generation on a single source; always aggregate with flags
- Do not log API keys or full response bodies
- Do not implement signal engine (scoring → Model_P) in this phase; only raw + normalized values
