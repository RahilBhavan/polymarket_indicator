"""Build reasoning payload: factor contributions, raw values, stale/missing."""

from typing import Any

from app.fetchers.base import FetcherResult
from app.signal.weights import get_weights


def missing_sources(
    results: list[FetcherResult],
    weights: dict[str, float] | None = None,
) -> list[str]:
    """Source IDs that are in weights but not present in results (failed or not run)."""
    w = weights or get_weights()
    present = {r.source_id for r in results}
    return [sid for sid in w if sid not in present]


def build_reasoning(results: list[FetcherResult]) -> list[dict[str, Any]]:
    """
    List of {factor_name, raw_value, contribution, stale, error}.
    contribution = normalized_score * weight (for display).
    """
    weights = get_weights()
    out = []
    for r in results:
        w = weights.get(r.source_id, 0.0)
        contrib = (r.normalized_score * w) if r.normalized_score is not None else None
        out.append(
            {
                "factor": r.source_id,
                "raw_value": r.raw_value,
                "contribution": round(contrib, 4) if contrib is not None else None,
                "stale": r.stale,
                "error": r.error,
            }
        )
    return out


def reasoning_summary(
    reasoning: list[dict[str, Any]],
    missing_sources_list: list[str] | None = None,
    max_factors: int = 3,
) -> str:
    """One-line summary: strongest bullish and bearish factors; missing sources if any."""
    with_contrib = [
        (x["factor"], x["contribution"] or 0)
        for x in reasoning
        if x.get("contribution") is not None
    ]
    with_contrib.sort(key=lambda t: t[1], reverse=True)
    top = with_contrib[:max_factors]
    bot = with_contrib[-max_factors:] if len(with_contrib) > max_factors else []
    parts = []
    if top:
        parts.append("Strong: " + ", ".join(f"{f}({c:+.2f})" for f, c in top))
    if bot and bot != top:
        parts.append("Weak: " + ", ".join(f"{f}({c:+.2f})" for f, c in bot))
    if missing_sources_list:
        parts.append("Missing: " + ", ".join(missing_sources_list))
    return "; ".join(parts) if parts else "No factors"
