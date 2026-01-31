# Polymarket integration specification

## APIs

- **Gamma Markets API**: Fetch markets (slug, question, end date, resolution source, condition_id, etc.). Filter for BTC daily markets (e.g. by slug pattern or tag).
- **CLOB API**: Order book (bids/asks), best bid/ask, depth. Use for Market_P (best ask for YES), spread, and max size at acceptable slippage.

## Market selection (BTC daily)

- Select the **active** daily BTC market for the target date (e.g. "Bitcoin above $X on YYYY-MM-DD").
- Prefer markets with sufficient liquidity (e.g. total depth > $10k) and clear resolution rules.
- Store in DB: market_condition_id, slug, resolution_source (exchange/index), end_date_utc.

## Order book and Market_P

- **Best ask** = price to buy YES (immediate fill). Use as Market_P for YES.
- **Best bid** = price to sell YES. Implied NO price ≈ 1 - best_bid (for binary).
- **Spread** = best_ask - best_bid. If spread > 0.05, warn "Use limit orders."
- **Depth**: Sum quantity (in shares or USD) up to price levels that keep volume-weighted slippage under SLIPPAGE_LIMIT. Return **max_safe_size_usd**.

## Resolution source parsing

- Each market has resolution metadata (e.g. "Binance BTC/USDT close at 23:59:59 UTC"). Parse and store so the **outcome job** queries the **same** feed (e.g. Binance API for that close price). Do not use CoinGecko if the market resolves on Binance.

## Authentication

- CLOB may require API key for higher rate limits. Gamma is often public. Document required env vars (e.g. POLYMARKET_CLOB_API_KEY if needed).

## BTC 15m Up/Down and live price feed

- **15m market selection:** Gamma `/events?series_id=...` (default `POLYMARKET_SERIES_ID_15M=10192`). Outcome labels `POLYMARKET_UP_LABEL` / `POLYMARKET_DOWN_LABEL` (default Up / Down).
- **Live BTC/USD price:** Polymarket WS `POLYMARKET_LIVE_WS_URL` (topic `crypto_prices_chainlink`); fallback Chainlink on Polygon: `POLYGON_RPC_URL`, `POLYGON_RPC_URLS`, `POLYGON_WSS_URLS`, `CHAINLINK_BTC_USD_AGGREGATOR`.
- **Proxy:** HTTP/HTTPS requests (Gamma, CLOB, Binance, Polygon RPC) respect `HTTPS_PROXY`, `HTTP_PROXY`, `ALL_PROXY`. WebSocket connections do not use proxy by default; see TROUBLESHOOTING.md.

### Environment variables (15m and live price)

| Variable | Purpose |
|----------|---------|
| `POLYMARKET_SERIES_ID_15M` | Gamma series ID for BTC 15m events (default `10192`) |
| `POLYMARKET_UP_LABEL` / `POLYMARKET_DOWN_LABEL` | Outcome labels (default `Up` / `Down`) |
| `POLYMARKET_LIVE_WS_URL` | Polymarket live WebSocket URL (e.g. `wss://ws-live-data.polymarket.com`) |
| `POLYGON_RPC_URL` / `POLYGON_RPC_URLS` | Polygon HTTP RPC for Chainlink fallback |
| `POLYGON_WSS_URL` / `POLYGON_WSS_URLS` | Polygon WSS for Chainlink log subscription |
| `CHAINLINK_BTC_USD_AGGREGATOR` | Chainlink BTC/USD aggregator address on Polygon |
| `CHAINLINK_HTTP_CACHE_SECONDS` | Min interval between Chainlink HTTP fetches (default 2) |
| `HTTPS_PROXY`, `HTTP_PROXY`, `ALL_PROXY`, `NO_PROXY` | Proxy for HTTP/HTTPS only; see TROUBLESHOOTING.md for WS limitations |
