"""Factor weights for composite score. Override via env (e.g. WEIGHT_ETF_FLOWS=0.25)."""

from app.config import get_settings

# PRD weights: ETF 25%, Exchange 20%, DXY 15%, FearGreed 10%, PriceMA 15%, Funding 10%, Macro 5%
DEFAULT_WEIGHTS: dict[str, float] = {
    "etf_flows": 0.25,
    "exchange_netflow": 0.20,
    "dxy": 0.15,
    "fear_greed": 0.10,
    "price_ma": 0.15,
    "funding": 0.10,
    "macro": 0.05,
}

# Optional fetchers: default 5% when enabled
DEFAULT_OPTIONAL_WEIGHTS: dict[str, float] = {
    "coinbase_premium": 0.05,
    "stablecoin_issuance": 0.05,
}

# Hourly Up/Down: short-horizon; heavier on 1h momentum + funding; zero ETF/DXY/macro
HOURLY_WEIGHTS: dict[str, float] = {
    "price_1h_momentum": 0.35,
    "funding": 0.20,
    "fear_greed": 0.15,
    "price_ma": 0.15,
    "exchange_netflow": 0.15,
    "etf_flows": 0.0,
    "dxy": 0.0,
    "macro": 0.0,
    "coinbase_premium": 0.0,
    "stablecoin_issuance": 0.0,
}


def get_weights() -> dict[str, float]:
    """Return factor weights; env overrides merged with defaults. Sum may be < 1 when optional fetchers disabled."""
    settings = get_settings()
    out = dict(DEFAULT_WEIGHTS)
    # Env overrides for core weights
    if settings.weight_etf_flows is not None:
        out["etf_flows"] = settings.weight_etf_flows
    if settings.weight_exchange_netflow is not None:
        out["exchange_netflow"] = settings.weight_exchange_netflow
    if settings.weight_dxy is not None:
        out["dxy"] = settings.weight_dxy
    if settings.weight_fear_greed is not None:
        out["fear_greed"] = settings.weight_fear_greed
    if settings.weight_price_ma is not None:
        out["price_ma"] = settings.weight_price_ma
    if settings.weight_funding is not None:
        out["funding"] = settings.weight_funding
    if settings.weight_macro is not None:
        out["macro"] = settings.weight_macro
    # Optional fetchers (only included when enabled)
    if settings.fetch_coinbase_premium:
        out["coinbase_premium"] = (
            settings.weight_coinbase_premium or DEFAULT_OPTIONAL_WEIGHTS["coinbase_premium"]
        )
    if settings.fetch_stablecoin_issuance:
        out["stablecoin_issuance"] = (
            settings.weight_stablecoin_issuance or DEFAULT_OPTIONAL_WEIGHTS["stablecoin_issuance"]
        )
    return out


def weighted_score(
    results: list[tuple[str, float | None]], weights: dict[str, float] | None = None
) -> float:
    """
    Composite score = sum(score_i * weight_i) for available results.
    Score range -2..+2; output clamped to [-2, 2].
    """
    w = weights or get_weights()
    total = 0.0
    total_weight = 0.0
    for source_id, score in results:
        if score is None:
            continue
        weight = w.get(source_id, 0.0)
        total += score * weight
        total_weight += weight
    if total_weight <= 0:
        return 0.0
    # Normalize by weight sum so partial data doesn't blow up
    raw = total / total_weight
    return max(-2.0, min(2.0, raw))
