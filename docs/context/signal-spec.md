# Signal specification: decision logic and sizing

## Decision flow

1. **Compute Model_P** from weighted factor scores (see data-sources and scoring).
2. **Fetch Market_P** from Polymarket (best ask for YES, or derive from bid for NO).
3. **Edge** = Model_P - Market_P_yes (when recommending YES) or (1 - Model_P) vs Market_P_no (when recommending NO). For simplicity we use: if Model_P > 0.5 signal YES side, edge = Model_P - best_ask_yes; else signal NO side, edge = (1 - Model_P) - best_bid_no_implied.
4. **Threshold**: Only produce a trade recommendation if Edge > EDGE_THRESHOLD (default 0.05 = 5%).
5. **Fee check**: Optionally reduce edge by estimated fee (e.g. 2%). If fee-adjusted edge < 0, output NO_TRADE.
6. **Liquidity check**: Compute max size such that slippage stays under SLIPPAGE_LIMIT (e.g. 1%). If recommended size > max size, cap and warn.

## Confidence mapping (score to Model_P)

- Composite score range: -2 to +2 (from factor weights).
- Map linearly or via table to Model_P in [0.15, 0.85] to avoid extremes (e.g. score +2 -> 0.85, score -2 -> 0.15, score 0 -> 0.50).
- Exact mapping must be documented in code and config.

## Sizing constraints

- **Fractional Kelly**: `k = f * (p*b - q) / b` where p = Model_P, q = 1-p, b = net odds (e.g. (1 - ask) / ask for YES). Default f = 0.25 (quarter-Kelly).
- **Cap by bankroll %**: Max stake = min(Kelly_result, MAX_BANKROLL_PCT * bankroll). Default MAX_BANKROLL_PCT = 0.05.
- **Cap by liquidity**: Max stake = liquidity-derived max (from order book depth at acceptable slippage).
- **Final recommended size** = min(Kelly_capped, liquidity_cap). Express in USD and as % of bankroll in the message.

## Configurable parameters (env or DB)

- EDGE_THRESHOLD (default 0.05)
- KELLY_FRACTION (default 0.25)
- MAX_BANKROLL_PCT (default 0.05)
- SLIPPAGE_LIMIT (default 0.01)
- DEFAULT_BANKROLL_USD (for users who don't set it; used only for recommendation display)
