"""Orchestrate: snapshot -> Model_P, Market_P, edge, size, reasoning."""

from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.fetchers.base import FetcherResult
from app.fetchers.registry import FeatureSnapshot
from app.polymarket.models import MarketQuote
from app.signal.edge import direction_from_edge
from app.signal.kelly import recommended_size_usd
from app.signal.reasoning import build_reasoning, missing_sources, reasoning_summary
from app.signal.score_to_prob import score_to_model_p
from app.signal.weights import weighted_score
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SignalResult:
    """Result of signal generation."""

    direction: str  # YES | NO | NO_TRADE
    model_p: float
    market_p: float
    edge: float
    recommended_usd: float
    reasoning: list[dict[str, Any]]
    reasoning_summary: str
    liquidity_warning: str | None
    market_slug: str | None
    market_condition_id: str | None
    # Display-only: shown in Telegram when user set bet cap or Kelly override
    user_bet_cap_usd: float | None = None
    kelly_fraction_used: float | None = None


def _results_to_score_tuples(results: list[FetcherResult]) -> list[tuple[str, float | None]]:
    return [(r.source_id, r.normalized_score) for r in results]


def _recommended_and_liquidity_warning(
    direction: str,
    model_p: float,
    market_p: float,
    bankroll_usd: float,
    quote: MarketQuote,
    max_bet_usd: float | None = None,
    kelly_fraction_override: float | None = None,
) -> tuple[float, str | None]:
    """Compute recommended size (USD) and optional liquidity warning for YES or NO."""
    if direction == "YES":
        rec = recommended_size_usd(
            model_p, market_p, bankroll_usd, quote.max_safe_size_usd,
            max_bet_usd=max_bet_usd, kelly_fraction_override=kelly_fraction_override,
        )
    elif direction == "NO":
        price_no = max(0.01, min(0.99, 1.0 - market_p))
        rec = recommended_size_usd(
            1.0 - model_p, price_no, bankroll_usd, quote.max_safe_size_usd,
            max_bet_usd=max_bet_usd, kelly_fraction_override=kelly_fraction_override,
        )
    else:
        return 0.0, None
    thin = quote.max_safe_size_usd < 100 or rec >= quote.max_safe_size_usd * 0.99
    warn = f"Thin liquidity. Max safe size: ${quote.max_safe_size_usd:.0f}" if thin else None
    return rec, warn


def run_engine(
    snapshot: FeatureSnapshot,
    quote: MarketQuote,
    market_slug: str | None = None,
    market_condition_id: str | None = None,
    bankroll_usd: float | None = None,
    weights: dict[str, float] | None = None,
    max_bet_usd: float | None = None,
    kelly_fraction_override: float | None = None,
) -> SignalResult:
    """
    Compute Model_P from snapshot, compare to quote, gate by edge, size with Kelly.
    Optional weights override default (e.g. HOURLY_WEIGHTS for hourly Up/Down).
    max_bet_usd caps recommended size; kelly_fraction_override overrides config kelly_fraction.
    """
    settings = get_settings()
    bankroll_usd = bankroll_usd or settings.default_bankroll_usd
    tuples = _results_to_score_tuples(snapshot.results)
    composite = weighted_score(tuples, weights=weights)
    model_p = score_to_model_p(composite)
    market_p = quote.implied_prob_yes
    market_bid = getattr(quote, "best_bid", None)
    direction, edge = direction_from_edge(model_p, market_p, market_bid)
    recommended_usd, liquidity_warning = _recommended_and_liquidity_warning(
        direction, model_p, market_p, bankroll_usd, quote,
        max_bet_usd=max_bet_usd, kelly_fraction_override=kelly_fraction_override,
    )
    reasoning = build_reasoning(snapshot.results)
    missing = missing_sources(snapshot.results)
    summary = reasoning_summary(reasoning, missing_sources_list=missing if missing else None)
    kelly_used = kelly_fraction_override if kelly_fraction_override is not None else None
    return SignalResult(
        direction=direction,
        model_p=model_p,
        market_p=market_p,
        edge=edge,
        recommended_usd=recommended_usd,
        reasoning=reasoning,
        reasoning_summary=summary,
        liquidity_warning=liquidity_warning,
        market_slug=market_slug,
        market_condition_id=market_condition_id,
        user_bet_cap_usd=max_bet_usd,
        kelly_fraction_used=kelly_used,
    )
