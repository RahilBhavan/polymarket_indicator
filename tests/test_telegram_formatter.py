"""Tests for Telegram signal message formatting (header, Up/Down labels)."""

from unittest.mock import MagicMock

from app.signal.engine import SignalResult
from app.telegram.formatter import format_signal_summary, format_signal_message


def _result(direction: str = "YES") -> SignalResult:
    return SignalResult(
        direction=direction,
        model_p=0.65,
        market_p=0.60,
        edge=0.05,
        recommended_usd=50.0,
        reasoning=[],
        reasoning_summary="test",
        liquidity_warning=None,
        market_slug=None,
        market_condition_id=None,
    )


def test_format_signal_summary_header_btc_daily_when_no_market() -> None:
    """When market is None, header is 'BTC Daily'."""
    result = _result()
    msg = format_signal_summary(result, market=None)
    assert "SIGNAL: BTC Daily" in msg
    assert "Direction: YES" in msg


def test_format_signal_summary_shows_up_down_when_market_has_labels() -> None:
    """When market has yes_label/no_label, direction shows Up/Down instead of YES/NO."""
    result_yes = _result(direction="YES")
    result_no = _result(direction="NO")
    result_nt = _result(direction="NO_TRADE")
    market = MagicMock()
    market.yes_label = "Up"
    market.no_label = "Down"
    market.slug = "bitcoin-up-or-down-january-31-2pm-et"

    msg_yes = format_signal_summary(result_yes, market=market)
    msg_no = format_signal_summary(result_no, market=market)
    msg_nt = format_signal_summary(result_nt, market=market)

    assert "Direction: Up" in msg_yes
    assert "Direction: Down" in msg_no
    assert "Direction: NO_TRADE" in msg_nt


def test_format_signal_summary_header_hourly_up_down_when_hourly_market() -> None:
    """When market is hourly Up/Down, header is 'BTC Hourly Up/Down'."""
    result = _result()
    market = MagicMock()
    market.yes_label = "Up"
    market.no_label = "Down"
    market.slug = "bitcoin-up-or-down-january-31-2pm-et"
    # is_btc_up_down_hourly_market checks slug; slug matches Up/Down pattern
    msg = format_signal_summary(result, market=market)
    assert "SIGNAL: BTC Hourly Up/Down" in msg or "BTC Hourly" in msg


def test_format_signal_message_accepts_market_none() -> None:
    """format_signal_message works with market=None (e.g. full details)."""
    result = _result()
    msg = format_signal_message(result, verbose=False, market=None)
    assert "BTC Daily" in msg
    assert "Direction: YES" in msg
