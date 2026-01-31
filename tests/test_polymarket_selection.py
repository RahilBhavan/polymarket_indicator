"""Tests for Polymarket market selection (daily and hourly Up/Down)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.polymarket.client import parse_market
from app.polymarket.selection import (
    is_btc_up_down_hourly_market,
    select_btc_market,
    select_btc_up_down_hourly_market,
    select_btc_up_down_hourly_markets_next_n,
)


def test_parse_market_outcomes_and_event_start_time() -> None:
    """parse_market correctly parses outcomes JSON string and eventStartTime."""
    raw = {
        "id": "1",
        "conditionId": "0xabc",
        "slug": "bitcoin-up-or-down-january-31-2pm-et",
        "endDate": "2026-01-31T20:00:00Z",
        "eventStartTime": "2026-01-31T19:00:00Z",
        "outcomes": '["Up", "Down"]',
        "active": True,
        "closed": False,
        "enableOrderBook": True,
    }
    m = parse_market(raw)
    assert m is not None
    assert m.event_start_time == "2026-01-31T19:00:00Z"
    assert m.outcomes_list == ["Up", "Down"]
    assert m.yes_label == "Up"
    assert m.no_label == "Down"


@pytest.mark.asyncio
async def test_select_btc_up_down_hourly_market_chooses_soonest_upcoming() -> None:
    """select_btc_up_down_hourly_market returns market with soonest event_start_time in future."""
    now = datetime(2026, 1, 31, 18, 0, 0, tzinfo=timezone.utc)
    raw_markets = [
        {
            "id": "1",
            "conditionId": "0xa",
            "slug": "bitcoin-up-or-down-january-31-2pm-et",
            "endDate": "2026-01-31T20:00:00Z",
            "eventStartTime": "2026-01-31T19:00:00Z",
            "outcomes": '["Up", "Down"]',
            "active": True,
            "closed": False,
            "enableOrderBook": True,
        },
        {
            "id": "2",
            "conditionId": "0xb",
            "slug": "bitcoin-up-or-down-january-31-3pm-et",
            "endDate": "2026-01-31T21:00:00Z",
            "eventStartTime": "2026-01-31T20:00:00Z",
            "outcomes": '["Up", "Down"]',
            "active": True,
            "closed": False,
            "enableOrderBook": True,
        },
    ]

    with patch("app.polymarket.selection.fetch_markets", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = raw_markets
        market = await select_btc_up_down_hourly_market(now_utc=now)
    assert market is not None
    assert market.condition_id == "0xa"
    assert market.slug == "bitcoin-up-or-down-january-31-2pm-et"
    assert market.event_start_time == "2026-01-31T19:00:00Z"


@pytest.mark.asyncio
async def test_select_btc_up_down_hourly_market_prefers_live_over_upcoming() -> None:
    """When a market is currently live (started, not ended), it is preferred over upcoming."""
    now = datetime(2026, 1, 31, 19, 30, 0, tzinfo=timezone.utc)
    raw_markets = [
        {
            "id": "1",
            "conditionId": "0xa",
            "slug": "bitcoin-up-or-down-january-31-2pm-et",
            "endDate": "2026-01-31T20:00:00Z",
            "eventStartTime": "2026-01-31T19:00:00Z",
            "outcomes": '["Up", "Down"]',
            "active": True,
            "closed": False,
            "enableOrderBook": True,
        },
        {
            "id": "2",
            "conditionId": "0xb",
            "slug": "bitcoin-up-or-down-january-31-3pm-et",
            "endDate": "2026-01-31T21:00:00Z",
            "eventStartTime": "2026-01-31T20:00:00Z",
            "outcomes": '["Up", "Down"]',
            "active": True,
            "closed": False,
            "enableOrderBook": True,
        },
    ]
    with patch("app.polymarket.selection.fetch_markets", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = raw_markets
        market = await select_btc_up_down_hourly_market(now_utc=now)
    assert market is not None
    assert market.condition_id == "0xa"
    assert "2pm" in (market.slug or "")


@pytest.mark.asyncio
async def test_select_btc_up_down_hourly_market_skips_past_event_start() -> None:
    """Markets that have ended (end_date in the past) are excluded."""
    now = datetime(2026, 1, 31, 20, 30, 0, tzinfo=timezone.utc)
    raw_markets = [
        {
            "id": "1",
            "conditionId": "0xa",
            "slug": "bitcoin-up-or-down-january-31-2pm-et",
            "endDate": "2026-01-31T20:00:00Z",
            "eventStartTime": "2026-01-31T19:00:00Z",
            "outcomes": '["Up", "Down"]',
            "active": True,
            "closed": False,
            "enableOrderBook": True,
        },
    ]
    with patch("app.polymarket.selection.fetch_markets", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = raw_markets
        market = await select_btc_up_down_hourly_market(now_utc=now)
    assert market is None


@pytest.mark.asyncio
async def test_select_btc_up_down_hourly_markets_next_n_returns_up_to_n() -> None:
    """select_btc_up_down_hourly_markets_next_n returns up to n markets (live + upcoming)."""
    now = datetime(2026, 1, 31, 18, 0, 0, tzinfo=timezone.utc)
    # Seven upcoming markets: event_start 19:00–01:00 (next day), all after now=18:00
    hours = [
        ("2026-01-31T19:00:00Z", "2026-01-31T20:00:00Z"),
        ("2026-01-31T20:00:00Z", "2026-01-31T21:00:00Z"),
        ("2026-01-31T21:00:00Z", "2026-01-31T22:00:00Z"),
        ("2026-01-31T22:00:00Z", "2026-01-31T23:00:00Z"),
        ("2026-01-31T23:00:00Z", "2026-02-01T00:00:00Z"),
        ("2026-02-01T00:00:00Z", "2026-02-01T01:00:00Z"),
        ("2026-02-01T01:00:00Z", "2026-02-01T02:00:00Z"),
    ]
    raw_markets = [
        {
            "id": str(i),
            "conditionId": f"0x{i}",
            "slug": f"bitcoin-up-or-down-january-31-{6 + i}pm-et",
            "endDate": end,
            "eventStartTime": start,
            "outcomes": '["Up", "Down"]',
            "active": True,
            "closed": False,
            "enableOrderBook": True,
        }
        for i, (start, end) in enumerate(hours)
    ]
    with patch("app.polymarket.selection.fetch_markets", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = raw_markets
        markets = await select_btc_up_down_hourly_markets_next_n(n=5, now_utc=now)
    assert len(markets) == 5
    assert all(m.slug and "up-or-down" in m.slug for m in markets)


@pytest.mark.asyncio
async def test_select_btc_market_prefers_hourly_then_daily() -> None:
    """select_btc_market returns hourly when available, else daily."""
    now = datetime(2026, 1, 31, 18, 0, 0, tzinfo=timezone.utc)
    hourly_raw = [
        {
            "id": "1",
            "conditionId": "0xa",
            "slug": "bitcoin-up-or-down-january-31-2pm-et",
            "endDate": "2026-01-31T20:00:00Z",
            "eventStartTime": "2026-01-31T19:00:00Z",
            "outcomes": '["Up", "Down"]',
            "active": True,
            "closed": False,
            "enableOrderBook": True,
        },
    ]
    with patch("app.polymarket.selection.fetch_markets", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = hourly_raw
        market = await select_btc_market(now_utc=now)
    assert market is not None
    assert "up-or-down" in (market.slug or "")


def test_is_btc_up_down_hourly_market() -> None:
    """is_btc_up_down_hourly_market True for Up/Down slug."""
    from app.polymarket.models import Market

    m = Market(
        id="1",
        conditionId="0x",
        slug="bitcoin-up-or-down-january-31-2pm-et",
    )
    assert is_btc_up_down_hourly_market(m) is True
    m2 = Market(id="2", conditionId="0y", slug="bitcoin-above-96500-on-january-30")
    assert is_btc_up_down_hourly_market(m2) is False
