"""Fractional Kelly sizing with bankroll and liquidity caps."""

from app.config import get_settings


def kelly_fraction(model_p: float, price_yes: float) -> float:
    """
    Kelly fraction for buying YES at price_yes. p = model_p, q = 1-p, b = (1 - price_yes) / price_yes (net odds).
    f* = (p*b - q) / b = p - q/b = p - (1-p)*price_yes/(1-price_yes). Cap at 0 if negative.
    """
    if price_yes <= 0 or price_yes >= 1:
        return 0.0
    q = 1 - model_p
    b = (1 - price_yes) / price_yes
    k = (model_p * b - q) / b
    return max(0.0, min(1.0, k))


def recommended_size_usd(
    model_p: float,
    market_p_yes: float,
    bankroll_usd: float,
    max_safe_size_usd: float,
) -> float:
    """
    Fractional Kelly * bankroll, capped by MAX_BANKROLL_PCT and by max_safe_size_usd.
    """
    settings = get_settings()
    k = kelly_fraction(model_p, market_p_yes)
    frac = settings.kelly_fraction
    cap_pct = settings.max_bankroll_pct
    size_kelly = bankroll_usd * k * frac
    size_cap_pct = bankroll_usd * cap_pct
    size_liquidity = max_safe_size_usd
    return round(min(size_kelly, size_cap_pct, size_liquidity), 2)
