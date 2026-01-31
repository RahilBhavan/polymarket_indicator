# Polymarket BTC 15m Assistant – Patterns We Re-Implement

Reference: [PolymarketBTC15mAssistant](https://github.com/FrondEnt/PolymarketBTC15mAssistant). We do **not** copy code; we re-implement the ideas in cryptosignal.

## Layered live BTC/USD price sources

1. **Polymarket live WebSocket** – Subscribe to `wss://ws-live-data.polymarket.com`, topic `crypto_prices_chainlink`. Same feed the Polymarket UI uses. Filter by symbol (btc).
2. **Chainlink on Polygon (WSS)** – Connect to Polygon WSS RPC, `eth_subscribe` to logs for the BTC/USD aggregator contract; decode `AnswerUpdated(int256,uint256,uint256)` for price and timestamp.
3. **Chainlink on Polygon (HTTP)** – Fallback: HTTP JSON-RPC `eth_call` for `latestRoundData()` and `decimals()` with short timeouts; rotate over multiple RPC URLs; cache result for a short interval (e.g. 2s) to avoid hammering.

Priority: Polymarket WS → Chainlink WSS → Chainlink HTTP.

## Series-based market selection

- Use Gamma **`/events?series_id=...`** (not just `/markets`) to get events for the BTC 15m series.
- Flatten events into markets (each event can have multiple markets; for 15m Up/Down we want the market per event).
- **Pick latest live market**: among markets with `endDate` in the future, prefer those already started (`eventStartTime` ≤ now); sort by `endDate` ascending and take the first (soonest-ending live window). If none live, take soonest upcoming.

## Up/Down market modeling

- Two outcomes: **Up** and **Down**. Each has a CLOB token ID and a buy price (and order book).
- Normalize market probabilities: `market_up = up_price / (up_price + down_price)`, `market_down = 1 - market_up` (or same from down_price).
- Edge: `edge_up = model_up - market_up`, `edge_down = model_down - market_down`. Decide BUY_UP / BUY_DOWN / NO_TRADE from best edge and thresholds.

## Time-left aware entry

- Phase by minutes remaining: e.g. EARLY (>10m), MID (5–10m), LATE (<5m).
- Stricter thresholds later: e.g. min edge 0.05 (EARLY), 0.10 (MID), 0.20 (LATE); min model probability 0.55 / 0.60 / 0.65.
- Apply time decay to raw model probability so that near settlement we don’t over-trade on weak signals.

## Operational pragmatism

- WebSocket: reconnect with backoff (e.g. 500ms, cap 10s); defensive JSON parse and numeric coercion; ignore malformed messages.
- HTTP: timeouts (e.g. 1.5s), retry over next RPC URL on failure.
- Proxy: support standard env vars (`HTTPS_PROXY`, `HTTP_PROXY`, `ALL_PROXY`) for both HTTP and WS where the client library allows.

## Console UX (optional)

- Stable “single screen”: move cursor to (0,0), clear below, then write current state (prices, TA, signal). Reduces log spam; some terminals may still vary.
