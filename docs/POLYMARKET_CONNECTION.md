# How Polymarket Is Connected to This Codebase

Polymarket is integrated via **public HTTP APIs** (no API key required for normal use) and an optional **WebSocket** for live BTC price. This doc maps where each connection lives and how data flows.

---

## 1. APIs Used

| Service | Base URL | Purpose |
|--------|----------|--------|
| **Gamma API** | `https://gamma-api.polymarket.com` | List markets/events, metadata (slug, conditionId, endDate, outcomes, clobTokenIds). |
| **CLOB API** | `https://clob.polymarket.com` | Order book (`/book`), best bid/ask, and price (`/price`) per outcome token. |
| **Polymarket WS** (optional) | `wss://ws-live-data.polymarket.com` | Live BTC/USD price (topic `crypto_prices_chainlink`) for price feed fallback. |

All HTTP calls use **httpx** (see `app/polymarket/client.py`). Proxy env vars (`HTTPS_PROXY`, etc.) apply to HTTP only; see TROUBLESHOOTING.md for WebSocket proxy limits.

---

## 2. Code Layout (Where Polymarket Is Wired)

```
src/app/
├── polymarket/
│   ├── client.py      # Gamma + CLOB HTTP: fetch_markets, fetch_order_book, fetch_events_by_series_id, fetch_clob_price
│   ├── models.py      # Market, OrderBook, MarketQuote, UpDownMarket, UpDownQuote
│   ├── selection.py   # select_btc_market() → hourly Up/Down or daily BTC by slug
│   ├── selection_15m.py  # select_btc_15m_updown_market(), build_updown_quote() via Gamma events + CLOB
│   └── depth.py      # max_safe_size_usd() from order book for sizing
├── live_prices/
│   └── polymarket_chainlink_ws.py  # WebSocket client for live BTC price (optional)
├── telegram/commands.py   # Uses select_btc_market, fetch_order_book, Polymarket event URLs
├── fetchers/registry.py   # Chooses fetchers/weights by market type (hourly vs daily)
├── signal/engine.py      # Uses MarketQuote (best_ask = market_p)
├── outcomes/recorder.py  # Fetches market by condition_id/slug for outcome resolution
└── config.py             # POLYMARKET_* and POLYGON_* / CHAINLINK_* for 15m and live price
```

---

## 3. Data Flow (How Polymarket Feeds the Signal)

1. **Market selection**  
   - **Hourly/daily** (`/signal`): `select_btc_market()` in `polymarket/selection.py`  
     - Calls Gamma `GET /markets?closed=false&end_date_min=...`, filters by slug patterns (e.g. `bitcoin.*up.*down`, `btc.*daily`), picks live or next upcoming hourly, else daily.  
   - **15m** (`/signal15m`): `select_btc_15m_updown_market()` in `polymarket/selection_15m.py`  
     - Calls Gamma `GET /events?series_id=...` (default `POLYMARKET_SERIES_ID_15M=10192`), flattens markets, picks current/next 15m window.

2. **Prices and order book**  
   - **Hourly/daily**: From Gamma market payload (`bestBid`/`bestAsk`) or CLOB `GET /book?token_id=<yes_token_id>` for the chosen market’s YES token.  
   - **15m**: CLOB `/book` and `/price` for both Up and Down tokens; `build_updown_quote()` builds `UpDownQuote` (normalized Up/Down probabilities, max safe size).

3. **Signal engine**  
   - Uses **market_p** = best ask (YES) or normalized Up/Down from CLOB. Compares to model probability, computes edge and recommended size (including `max_safe_size_usd` from `polymarket/depth.py`).

4. **Outcomes**  
   - EOD job uses `market_condition_id` / slug; recorder fetches market from Gamma (`fetch_markets`/`parse_market`) to resolve WIN/LOSS.

5. **Live BTC price** (optional)  
   - `polymarket_chainlink_ws.py` subscribes to Polymarket WS; `price_feed.py` can use it before falling back to Chainlink on Polygon.

---

## 4. Configuration (Connecting / Tuning Polymarket)

All Polymarket-related settings are in **environment variables** (see `.env.example` and `app/config.py`). You don’t need an API key for Gamma or CLOB for normal usage.

| Variable | Default | Purpose |
|----------|---------|--------|
| `POLYMARKET_SERIES_ID_15M` | `10192` | Gamma series_id for BTC 15m Up/Down events. |
| `POLYMARKET_UP_LABEL` / `POLYMARKET_DOWN_LABEL` | `Up` / `Down` | Outcome labels when parsing 15m markets. |
| `POLYMARKET_LIVE_WS_URL` | `wss://ws-live-data.polymarket.com` | Live data WebSocket (e.g. BTC price). |
| `POLYGON_RPC_URL`, `POLYGON_RPC_URLS` | (see config) | Polygon RPC for Chainlink fallback if not using Polymarket WS. |
| `CHAINLINK_BTC_USD_AGGREGATOR` | (Polygon address) | Chainlink BTC/USD on Polygon for fallback price. |
| `POLYMARKET_API_KEY` | (optional) | Polymarket API key (Builder Keys at polymarket.com/settings?tab=builder). Sent as `Authorization: Bearer <key>` on Gamma and CLOB requests for higher rate limits. Set in `.env` only; never commit. |
| `POLYMARKET_BTC_HOURLY_SLUG` | (optional) | Pin `/signal` to a specific hourly market when active (e.g. `bitcoin-up-or-down-january-31-5pm-et`). Use `/hourly5` for predictions for the next 5 hours and links to place bets in advance. |

For **hourly/daily** markets, selection is by **slug patterns** in code (`polymarket/selection.py`: `BTC_DAILY_PATTERNS`, `BTC_UP_DOWN_HOURLY_PATTERNS`). No extra env is required; ensure Polymarket has active BTC hourly or daily markets that match those patterns.

---

## 5. Adding or Changing Polymarket Usage

- **Different 15m series**  
  Set `POLYMARKET_SERIES_ID_15M` to another Gamma series_id that has 15m Up/Down events.

- **Different outcome labels**  
  Set `POLYMARKET_UP_LABEL` / `POLYMARKET_DOWN_LABEL` if the event uses different names (e.g. "Higher" / "Lower").

- **New market types (e.g. ETH, other timeframes)**  
  - Add slug patterns or a Gamma filter (e.g. tag/series) in a new or existing function in `polymarket/selection.py` or a new module.  
  - Reuse `fetch_markets`, `fetch_order_book`, `fetch_clob_price`, and `parse_market` / `parse_updown_market` from `polymarket/client.py`.  
  - In `telegram/commands.py` (or a new command), call your selector, then build a quote and run the appropriate engine (reuse or extend `run_engine` / 15m engine).

- **CLOB API key (higher rate limits)**  
  Gamma/CLOB are used without auth today. If you add an API key later, extend `app/polymarket/client.py`: pass a header (e.g. `Authorization` or Polymarket’s key header) in the httpx client for CLOB requests and document the new env var (e.g. `POLYMARKET_CLOB_API_KEY`) in this doc and `.env.example`.

---

## 6. Quick Reference: Key Functions

| Function | Module | Role |
|----------|--------|------|
| `fetch_markets(...)` | `polymarket/client.py` | Gamma: list markets (slug, end_date_min, closed, limit). |
| `fetch_events_by_series_id(series_id)` | `polymarket/client.py` | Gamma: list events (for 15m by series_id). |
| `fetch_order_book(token_id)` | `polymarket/client.py` | CLOB: order book for one outcome token. |
| `fetch_clob_price(token_id, side)` | `polymarket/client.py` | CLOB: buy/sell price for one token. |
| `select_btc_market()` | `polymarket/selection.py` | Picks hourly Up/Down (live or upcoming) or daily BTC market. |
| `select_btc_15m_updown_market()` | `polymarket/selection_15m.py` | Picks current/next BTC 15m Up/Down market. |
| `build_updown_quote(market)` | `polymarket/selection_15m.py` | Builds UpDownQuote from CLOB for Up/Down tokens. |
| `max_safe_size_usd(book, side)` | `polymarket/depth.py` | Max size at acceptable slippage from order book. |

Together, these form the Polymarket connection: **Gamma for discovery and metadata, CLOB for trading prices and depth**, and optional **Polymarket WS** for live BTC price.

---

## 7. "No active BTC market" message

If the bot replies with **"No active BTC market found (hourly Up/Down or daily)"**, it still sends an **analytical view** (model vs 50% reference). Possible causes:

1. **No hourly/daily market listed** – Polymarket may not have an open BTC hourly Up/Down or daily market for the current time (e.g. between windows).
2. **Gamma API** – Ensure `POLYMARKET_API_KEY` is set if your environment needs it. Check logs for `select_hourly_no_candidates` or `select_btc_up_down_hourly_no_market` to see `raw_count` and `sample_slugs` returned by Gamma.
3. **Pinned slug** – If `POLYMARKET_BTC_HOURLY_SLUG` is set, the bot tries that market first; if it’s past or closed, no other market is tried. Clear the env or set it to a current slug (e.g. `bitcoin-up-or-down-january-31-5pm-et`).

Market selection prefers **live** (event started, not ended) then **upcoming** hourly markets; if Gamma omits `eventStartTime`, markets with `endDate` in the future are still considered.
