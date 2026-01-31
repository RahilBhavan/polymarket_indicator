"""Sanity bounds for raw fetcher values. Reject or flag impossible values before normalize()."""

from app.fetchers.base import FetcherResult

# (min, max) inclusive for numeric raw values. None means no bound on that side.
# fear_greed: index 0-100
# funding: rate as decimal, typically ±0.01 (1%); use ±0.05 for sanity
# dxy: 5d trend %; ±20% is a wide but plausible range
# price_ma: % deviation from MA; ±30% extreme move
# etf_flows: daily net flow in $M; ±5000 is very wide
RAW_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "fear_greed": (0.0, 100.0),
    "funding": (-0.05, 0.05),
    "dxy": (-20.0, 20.0),
    "price_ma": (-30.0, 30.0),
    "etf_flows": (-5000.0, 5000.0),
    "exchange_netflow": (-100_000.0, 100_000.0),
    "macro": (None, None),  # not numeric raw
    "coinbase_premium": (-0.1, 0.1),
    "stablecoin_issuance": (-50.0, 50.0),  # % 24h change
}


def check_bounds(
    source_id: str,
    raw_value: float | None,
) -> bool:
    """
    Return True if raw_value is within defined bounds for source_id.
    Return False if out of bounds or source_id has no bounds (then True).
    """
    if raw_value is None:
        return True
    bounds = RAW_BOUNDS.get(source_id)
    if bounds is None:
        return True
    lo, hi = bounds
    if lo is not None and raw_value < lo:
        return False
    if hi is not None and raw_value > hi:
        return False
    return True


def out_of_range_result(source_id: str) -> FetcherResult:
    """Build FetcherResult with error='out_of_range' for the given source."""
    return FetcherResult(
        source_id=source_id,
        raw_value=None,
        normalized_score=None,
        stale=False,
        error="out_of_range",
    )
