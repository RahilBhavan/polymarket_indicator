# Phase 4 — Signal engine v1 (EV / edge)

## Purpose

Implement deterministic edge model: factor weights, composite score → Model_P, compare to Market_P, edge threshold gating, fractional Kelly sizing with bankroll and liquidity caps, and reasoning payload (raw values + staleness flags).

## Attach in Cursor

- This file
- `docs/context/domain.md`
- `docs/context/signal-spec.md`
- `docs/context/data-sources.md`
- Phase 2–3 code: polymarket client, fetchers, feature snapshot storage

## Files to create/modify

- `src/app/signal/weights.py` — factor weights (configurable or constant): ETF 25%, Exchange 20%, DXY 15%, FearGreed 10%, PriceMA 15%, Funding 10%, Macro 5%
- `src/app/signal/score_to_prob.py` — map composite score (-2..+2) to Model_P in [0.15, 0.85]; document formula
- `src/app/signal/edge.py` — compute Edge = Model_P - Market_P_yes (when recommending YES); for NO, use (1 - Model_P) vs NO side price; apply EDGE_THRESHOLD (default 0.05)
- `src/app/signal/kelly.py` — fractional Kelly: k = f * (p*b - q) / b; cap by MAX_BANKROLL_PCT * bankroll and by liquidity max_safe_size_usd
- `src/app/signal/reasoning.py` — build reasoning payload: list of (factor_name, raw_value, contribution, stale); strongest bullish/bearish; missing sources
- `src/app/signal/engine.py` — orchestrate: load snapshot, compute composite score → Model_P; get Market_P and depth from Polymarket; compute edge; if edge < threshold return NO_TRADE; else compute size (Kelly + caps); build reasoning; return SignalResult(direction, model_p, market_p, edge, recommended_usd, reasoning, liquidity_warning)
- `src/app/db/signal_runs.py` — insert signal run (run_at, market_slug, direction, model_p, market_p, edge, recommended_usd, reasoning_json, liquidity_warning, status)
- Config: EDGE_THRESHOLD, KELLY_FRACTION, MAX_BANKROLL_PCT, SLIPPAGE_LIMIT, DEFAULT_BANKROLL_USD
- Wire: daily job (or /signal) calls fetchers → snapshot → engine → store → send Telegram message (use message-spec format)

## Acceptance criteria

- Model_P in [0.15, 0.85]; Edge = Model_P - Market_P_yes when direction YES; when edge < 0.05, direction NO_TRADE
- Recommended size = min(Kelly_capped, liquidity_cap); never exceed MAX_BANKROLL_PCT * bankroll
- Reasoning includes each factor raw value and contribution; stale/missing flagged
- Every signal run persisted to Postgres with all inputs and outputs
- Telegram message shows: direction, model confidence %, market price, edge %, recommended bet, reasoning line, liquidity warning if any

## Testing checklist

- Unit test: score_to_prob at boundaries (-2, 0, +2)
- Unit test: edge gating (edge < 0.05 → NO_TRADE)
- Unit test: Kelly formula and caps (bankroll cap, liquidity cap)
- Unit test: reasoning builder with partial data (one source missing)
- Integration test: full engine run with mock snapshot and mock Polymarket response; result shape and NO_TRADE when edge too low

## Do not do

- Do not use an LLM for trading logic; all logic deterministic
- Do not recommend size above liquidity cap without warning
- Do not skip storing raw inputs and outputs for the run
