# Data sources: APIs, freshness, normalization

## Source list (PRD + improvement)

| Source | Data point | API / method | Update frequency | Weight (reference) |
|--------|------------|--------------|------------------|--------------------|
| ETF Flows | Daily net flow ($) | SoSoValue | After US close | 25–30% |
| Exchange flow | 7d netflow (BTC) | CryptoQuant / Glassnode (paid) | Hourly agg | 20% |
| DXY | 5d trend % | Yahoo Finance | At signal time | 15% |
| Fear & Greed | Index 0–100 | alternative.me | Daily | 10% |
| Price vs MA | % deviation (e.g. 50MA) | Binance / CoinGecko | Real-time | 15% |
| Funding rate | Perp funding % | Binance Futures / Bybit | Every 8h | 10% |
| Macro | Calendar (FOMC/CPI within 48h) | FMP economic calendar (optional key) | Daily | 5% |
| (Optional) Coinbase premium | US vs global spread | CryptoQuant / TradingView | At signal time | See PRD improvement |
| (Optional) Stablecoin issuance | 24h market cap % change | CoinGecko markets (USDT/USDC) | Daily | See PRD improvement |

**Exchange netflow**: No free API; CryptoQuant/Glassnode are paid. Set `WEIGHT_EXCHANGE_NETFLOW=0` or omit API key to disable; fetcher returns `no_api_key`.

**Macro**: FMP (Financial Modeling Prep) economic calendar when `FMP_API_KEY` is set; otherwise fallback `no_event` (score 0.5). Free tier: 250 calls/day.

**Stablecoin issuance**: CoinGecko `/coins/markets` for tether + usd-coin; uses `market_cap_change_percentage_24h` as proxy for supply change. Optional fetcher: enable with `FETCH_STABLECOIN_ISSUANCE=true`.

## Normalization rules

- Each fetcher returns a **raw value** and a **normalized score** in a defined range (e.g. -2 to +2) or a **contribution** to Model_P.
- **Staleness**: If data older than MAX_AGE (e.g. 24h for daily, 8h for funding), mark as stale and still use but flag in reasoning. Staleness is set from API timestamps where available (Fear & Greed, DXY, Funding, Price/MA, ETF if API returns date/updated/timestamp). Where the API does not return a timestamp, data is treated as "assumed fresh".
- **Missing**: If a source fails (circuit open, timeout), omit from composite; reduce effective weight sum; flag "Source X unavailable" in reasoning.
- **Fallback**: For price, Binance primary and CoinGecko fallback (e.g. on 451). When both succeed, a **price cross-check** runs: if Binance and CoinGecko last-close differ by more than 1%, the result is marked stale so downstream can treat it as lower confidence.
- **Sanity bounds**: Raw values are checked against per-source bounds before normalize. If out of range (e.g. Fear & Greed outside 0–100, funding outside ±5%), the fetcher returns `error="out_of_range"` and no score.

## Data quality and analyzable dataset

- **Outcome reliability**: Analyzable "solid" data assumes the EOD outcomes job runs so that resolved runs get `outcome` (WIN/LOSS) and `actual_result` (YES/NO) set. Any run with `outcome IS NULL` after the market has ended is excluded from backtest and feature–outcome analysis.
- **Feature + outcome history**: Use `fetch_resolved_runs_with_features(date_from, date_to)` (see `app.db.feature_snapshots`) to get, for each resolved run in a date range, `run_at`, `outcome`, `actual_result`, `model_p`, and one row per source with `source_id`, `raw_value`, `normalized_score`, `stale`. Optional export: `scripts/export_feature_outcomes.py` writes CSV for notebooks or external tools.
- **Validation script**: `scripts/validate_data_sources.py` runs all fetchers, prints per-source status and raw values, and exits non-zero if more than N sources failed or a critical source (e.g. price_ma) is missing.

## Storage

- Every signal run stores a **feature snapshot** (timestamp, source_id, raw_value, normalized_score, stale) in Postgres for reproducibility and backtest.
