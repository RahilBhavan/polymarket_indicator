"""Phase 5: Unit tests for outcome resolution (parse rule, resolve YES/NO, Up/Down 1h)."""

from datetime import datetime, timezone

import httpx
import pytest
import respx

from app.outcomes.resolution import (
    is_binance_resolution,
    is_up_down_market,
    parse_rule_from_question,
    resolve_outcome,
    resolve_up_down_1h,
)


def test_parse_rule_above() -> None:
    """Parse 'above $96,500' from question/slug."""
    rule_above, rule_below = parse_rule_from_question("Bitcoin above $96,500 on January 30?")
    assert rule_above == 96500.0
    assert rule_below is None


def test_parse_rule_above_no_comma() -> None:
    """Parse 'above $96500' (no comma)."""
    rule_above, rule_below = parse_rule_from_question("Will Bitcoin be above $96500 on 2026-01-30?")
    assert rule_above == 96500.0
    assert rule_below is None


def test_parse_rule_below() -> None:
    """Parse 'below $97,000'."""
    rule_above, rule_below = parse_rule_from_question("Bitcoin below $97,000 on Jan 30")
    assert rule_above is None
    assert rule_below == 97000.0


def test_parse_rule_at_or_above() -> None:
    """Parse 'at or above $96,500' from question."""
    rule_above, rule_below = parse_rule_from_question("Bitcoin at or above $96,500 on January 30?")
    assert rule_above == 96500.0
    assert rule_below is None


def test_parse_rule_above_or_equal() -> None:
    """Parse 'above or equal $97,000'."""
    rule_above, rule_below = parse_rule_from_question("Will BTC be above or equal $97,000?")
    assert rule_above == 97000.0
    assert rule_below is None


def test_parse_rule_gte_symbol() -> None:
    """Parse '>= $96,500'."""
    rule_above, rule_below = parse_rule_from_question("Price >= $96,500 at expiry")
    assert rule_above == 96500.0
    assert rule_below is None


def test_parse_rule_at_or_below() -> None:
    """Parse 'at or below $97,000'."""
    rule_above, rule_below = parse_rule_from_question("Bitcoin at or below $97,000 on Jan 30")
    assert rule_above is None
    assert rule_below == 97000.0


def test_parse_rule_below_or_equal() -> None:
    """Parse 'below or equal $96,000'."""
    rule_above, rule_below = parse_rule_from_question("BTC below or equal $96,000")
    assert rule_above is None
    assert rule_below == 96000.0


def test_parse_rule_lte_symbol() -> None:
    """Parse '<= $97,000'."""
    rule_above, rule_below = parse_rule_from_question("Close <= $97,000")
    assert rule_above is None
    assert rule_below == 97000.0


def test_parse_rule_none() -> None:
    """No rule in text returns (None, None)."""
    assert parse_rule_from_question("Some other market") == (None, None)
    assert parse_rule_from_question(None) == (None, None)
    assert parse_rule_from_question("") == (None, None)


def test_resolve_outcome_above_yes() -> None:
    """Close 96,600 vs strike above 96,500 -> YES."""
    result = resolve_outcome(None, 96600.0, 96500.0, None)
    assert result == "YES"


def test_resolve_outcome_above_no() -> None:
    """Close 96,400 vs strike above 96,500 -> NO."""
    result = resolve_outcome(None, 96400.0, 96500.0, None)
    assert result == "NO"


def test_resolve_outcome_above_exact() -> None:
    """Close equals strike above -> YES (>=)."""
    result = resolve_outcome(None, 96500.0, 96500.0, None)
    assert result == "YES"


def test_resolve_outcome_below_yes() -> None:
    """Close 96,000 vs strike below 97,000 -> YES (close <= rule_below)."""
    result = resolve_outcome(None, 96000.0, None, 97000.0)
    assert result == "YES"


def test_resolve_outcome_below_no() -> None:
    """Close 97,500 vs strike below 97,000 -> NO."""
    result = resolve_outcome(None, 97500.0, None, 97000.0)
    assert result == "NO"


def test_resolve_outcome_no_close_returns_none() -> None:
    """Insufficient data (no close price) returns None."""
    assert resolve_outcome(None, None, 96500.0, None) is None


def test_resolve_outcome_no_rule_returns_none() -> None:
    """No rule (both rule_above and rule_below None) returns None."""
    assert resolve_outcome(None, 96600.0, None, None) is None


def test_is_binance_resolution() -> None:
    """Binance in resolution_source returns True."""
    assert is_binance_resolution("Binance BTC/USDT close at 23:59 UTC") is True
    assert is_binance_resolution("binance") is True
    assert is_binance_resolution(None) is False
    assert is_binance_resolution("Coinbase BTC close") is False


def test_is_up_down_market_by_outcomes() -> None:
    """Up/Down detected via outcomes ['Up', 'Down']."""
    assert is_up_down_market(None, ["Up", "Down"]) is True
    assert is_up_down_market("anything", ["Up", "Down"]) is True
    assert is_up_down_market(None, ["Yes", "No"]) is False


def test_is_up_down_market_by_question() -> None:
    """Up/Down detected via question/slug containing 'Up or Down' or 'up/down'."""
    assert is_up_down_market("Bitcoin Up or Down - January 31, 2PM ET") is True
    assert is_up_down_market("bitcoin-up-or-down-january-31-2pm-et") is True
    assert is_up_down_market("Bitcoin above $96,500") is False
    assert is_up_down_market(None) is False


@respx.mock
@pytest.mark.asyncio
async def test_resolve_up_down_1h_yes_when_close_ge_open() -> None:
    """resolve_up_down_1h returns YES when close >= open."""
    # Candle 19:00-20:00 UTC: open 97000, close 97100
    start_ts = int(datetime(2026, 1, 31, 19, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    respx.get("https://api.binance.com/api/v3/klines").mock(
        return_value=httpx.Response(
            200,
            json=[[start_ts, "97000", "97200", "96900", "97100", "1000"]],
        )
    )
    end_date_utc = datetime(2026, 1, 31, 20, 0, 0, tzinfo=timezone.utc)
    result = await resolve_up_down_1h(end_date_utc)
    assert result == "YES"


@respx.mock
@pytest.mark.asyncio
async def test_resolve_up_down_1h_no_when_close_lt_open() -> None:
    """resolve_up_down_1h returns NO when close < open."""
    start_ts = int(datetime(2026, 1, 31, 19, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    respx.get("https://api.binance.com/api/v3/klines").mock(
        return_value=httpx.Response(
            200,
            json=[[start_ts, "97100", "97200", "96900", "97000", "1000"]],
        )
    )
    end_date_utc = datetime(2026, 1, 31, 20, 0, 0, tzinfo=timezone.utc)
    result = await resolve_up_down_1h(end_date_utc)
    assert result == "NO"


def test_fetch_1h_open_close_binance_returns_tuple() -> None:
    """fetch_1h_open_close_binance is async; test via resolve_up_down_1h above."""
    pass
