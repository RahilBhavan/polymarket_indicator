"""Signal engine: score_to_prob, edge gating, Kelly, reasoning, engine."""

import os
from app.fetchers.base import FetcherResult
from app.fetchers.registry import FeatureSnapshot
from app.polymarket.models import MarketQuote
from app.signal.edge import compute_edge, direction_from_edge, edge_above_threshold
from app.signal.engine import run_engine
from app.signal.kelly import kelly_fraction, recommended_size_usd
from app.signal.reasoning import build_reasoning, missing_sources, reasoning_summary
from app.signal.score_to_prob import score_to_model_p
from app.signal.weights import get_weights


def test_score_to_model_p() -> None:
    """Map -2, 0, +2 to 0.15, 0.5, 0.85."""
    assert score_to_model_p(-2) == 0.15
    assert score_to_model_p(0) == 0.5
    assert score_to_model_p(2) == 0.85
    assert 0.15 <= score_to_model_p(0.5) <= 0.85


def test_compute_edge() -> None:
    """Edge = model_p - market_p_yes."""
    assert compute_edge(0.70, 0.60) == 0.10
    assert compute_edge(0.50, 0.60) == -0.10


def test_edge_above_threshold() -> None:
    """Default threshold 0.05."""
    os.environ.setdefault("EDGE_THRESHOLD", "0.05")
    assert edge_above_threshold(0.06) is True
    assert edge_above_threshold(0.04) is False


def test_direction_from_edge_yes() -> None:
    """Edge yes >= 0.05 -> YES."""
    direction, edge = direction_from_edge(0.75, 0.65, market_bid=0.60)
    assert direction == "YES"
    assert edge == 0.10


def test_direction_from_edge_no_trade() -> None:
    """Edge yes < 0.05 and edge no < 0.05 -> NO_TRADE."""
    direction, _ = direction_from_edge(0.52, 0.50, market_bid=0.48)
    assert direction == "NO_TRADE"


def test_kelly_fraction() -> None:
    """Kelly for YES at price; cap 0-1."""
    k = kelly_fraction(0.70, 0.60)
    assert k >= 0
    assert k <= 1


def test_recommended_size_usd() -> None:
    """Capped by bankroll % and liquidity."""
    size = recommended_size_usd(0.70, 0.60, 1000.0, 500.0)
    assert size >= 0
    assert size <= 500
    assert size <= 50  # 5% of 1000


def test_run_engine() -> None:
    """Engine returns SignalResult with direction, model_p, edge."""
    snapshot = FeatureSnapshot(
        results=[
            FetcherResult("etf_flows", "100", 1.0, False),
            FetcherResult("funding", "0.01", 0.0, False),
            FetcherResult("dxy", "-0.5", 1.0, False),
        ],
        timestamp="2026-01-30T12:00:00Z",
    )
    quote = MarketQuote(
        best_bid=0.55,
        best_ask=0.60,
        spread=0.05,
        implied_prob_yes=0.60,
        max_safe_size_usd=300.0,
    )
    result = run_engine(snapshot, quote, market_slug="btc-daily")
    assert result.direction in ("YES", "NO", "NO_TRADE")
    assert 0.15 <= result.model_p <= 0.85
    assert result.market_p == 0.60
    assert result.reasoning
    assert result.reasoning_summary


def test_run_engine_no_trade_when_edge_below_threshold() -> None:
    """When edge < 0.05, direction is NO_TRADE."""
    os.environ.setdefault("EDGE_THRESHOLD", "0.05")
    snapshot = FeatureSnapshot(
        results=[
            FetcherResult("etf_flows", "0", 0.0, False),
            FetcherResult("funding", "0.01", 0.0, False),
            FetcherResult("dxy", "0", 0.0, False),
        ],
        timestamp="2026-01-30T12:00:00Z",
    )
    quote = MarketQuote(
        best_bid=0.50,
        best_ask=0.50,
        spread=0.0,
        implied_prob_yes=0.50,
        max_safe_size_usd=500.0,
    )
    result = run_engine(snapshot, quote)
    assert result.direction == "NO_TRADE"
    assert 0.15 <= result.model_p <= 0.85
    assert result.recommended_usd == 0.0


def test_reasoning_partial_data_missing_sources() -> None:
    """Reasoning with one source missing: missing_sources lists it; summary can include Missing."""
    results = [
        FetcherResult("etf_flows", "100", 1.0, False),
        FetcherResult("dxy", "-0.5", 0.5, False),
    ]
    reasoning = build_reasoning(results)
    weights = get_weights()
    missing = missing_sources(results, weights)
    assert "etf_flows" in [r["factor"] for r in reasoning]
    assert "dxy" in [r["factor"] for r in reasoning]
    assert len(missing) > 0
    assert "funding" in missing or "exchange_netflow" in missing
    summary = reasoning_summary(reasoning, missing_sources_list=missing)
    assert "Missing:" in summary
