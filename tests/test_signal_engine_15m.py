"""Tests for 15m Up/Down signal engine (edge, time-left, sizing)."""

from unittest.mock import patch

import pytest

from app.polymarket.models import UpDownQuote
from app.signal.engine_15m import (
    run_engine_15m,
    _apply_time_awareness,
    _compute_edge_up_down,
    _decide,
    _score_direction,
)


def test_apply_time_awareness() -> None:
    """Time decay: raw_up moves toward 0.5 as remaining_minutes decreases."""
    up, down = _apply_time_awareness(0.7, 15.0, 15.0)
    assert up == 0.7
    assert down == pytest.approx(0.3)
    up, down = _apply_time_awareness(0.7, 0.0, 15.0)
    assert up == 0.5
    assert down == 0.5
    up, down = _apply_time_awareness(0.7, 7.5, 15.0)
    assert 0.5 < up < 0.7
    assert 0.3 < down < 0.5


def test_compute_edge_up_down() -> None:
    """Edge = model - market (normalized)."""
    edge_up, edge_down = _compute_edge_up_down(0.6, 0.4, 0.5, 0.5)
    assert edge_up == 0.1
    assert edge_down == -0.1
    edge_up, edge_down = _compute_edge_up_down(0.55, 0.45, 0.6, 0.4)
    assert edge_up == -0.05
    assert edge_down == 0.05


def test_decide_no_trade_when_edge_below_threshold() -> None:
    """decide returns NO_TRADE when best edge below phase threshold."""
    direction, phase = _decide(12.0, 0.02, 0.01, 0.6, 0.4)  # EARLY threshold 0.05
    assert direction == "NO_TRADE"
    assert phase == "EARLY"


def test_decide_buy_up_when_edge_up_sufficient() -> None:
    """decide returns BUY_UP when edge_up >= threshold and model_up >= min_prob."""
    direction, phase = _decide(12.0, 0.08, 0.02, 0.6, 0.4)
    assert direction == "BUY_UP"
    assert phase == "EARLY"


def test_decide_buy_down_when_edge_down_sufficient() -> None:
    """decide returns BUY_DOWN when edge_down >= threshold and model_down >= min_prob."""
    direction, phase = _decide(12.0, 0.02, 0.08, 0.4, 0.6)
    assert direction == "BUY_DOWN"
    assert phase == "EARLY"


def test_decide_no_trade_when_model_prob_below_min() -> None:
    """decide returns NO_TRADE when best model prob below phase min_prob."""
    direction, phase = _decide(12.0, 0.10, 0.0, 0.52, 0.48)  # EARLY min_prob 0.55
    assert direction == "NO_TRADE"


def test_score_direction_bullish_when_price_above_vwap() -> None:
    """score_direction returns higher raw_up when price > vwap."""
    raw = _score_direction(100.0, 99.0, 0.5, 55.0, 0.1, None, "green", 2, False)
    assert raw > 0.5


def test_score_direction_bearish_when_price_below_vwap() -> None:
    """score_direction returns lower raw_up when price < vwap."""
    raw = _score_direction(98.0, 99.0, -0.5, 45.0, -0.1, None, "red", 2, False)
    assert raw < 0.5


def test_run_engine_15m_no_trade_on_insufficient_klines() -> None:
    """run_engine_15m returns NO_TRADE when candles_1m too short."""
    quote = UpDownQuote(
        up_buy_price=0.55,
        down_buy_price=0.45,
        market_up_norm=0.55,
        market_down_norm=0.45,
        max_safe_up_usd=500.0,
        max_safe_down_usd=500.0,
    )
    result = run_engine_15m(
        quote=quote,
        remaining_minutes=10.0,
        bankroll_usd=1000.0,
        candles_1m=[],  # insufficient
    )
    assert result.direction == "NO_TRADE"
    assert result.recommended_usd == 0.0


def test_run_engine_15m_sizing_capped_by_liquidity() -> None:
    """run_engine_15m recommended_usd is capped by max_safe_*_usd."""
    quote = UpDownQuote(
        up_buy_price=0.5,
        down_buy_price=0.5,
        market_up_norm=0.4,
        market_down_norm=0.6,
        max_safe_up_usd=50.0,
        max_safe_down_usd=50.0,
    )
    # Build minimal 1m klines: 30 candles so RSI/MACD etc. can run
    candles = []
    base = 97000.0
    for i in range(30):
        o = base + i * 10
        c = base + i * 10 + 5
        h = c + 20
        l = o - 20
        vol = 100.0
        candles.append([0, o, h, l, c, vol])
    result = run_engine_15m(
        quote=quote,
        remaining_minutes=10.0,
        bankroll_usd=10000.0,
        candles_1m=candles,
    )
    assert result.direction in ("BUY_UP", "BUY_DOWN", "NO_TRADE")
    if result.direction == "BUY_UP":
        assert result.recommended_usd <= 50.0
    elif result.direction == "BUY_DOWN":
        assert result.recommended_usd <= 50.0
    assert result.model_up + result.model_down == pytest.approx(1.0)
    assert result.market_up_norm + result.market_down_norm == pytest.approx(1.0)
