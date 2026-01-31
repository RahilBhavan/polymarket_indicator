"""Tests for BTC 15m Up/Down market selection (Gamma events, pick latest live)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.polymarket.client import parse_updown_market
from app.polymarket.selection_15m import (
    flatten_event_markets,
    pick_latest_live_market,
    select_btc_15m_updown_market,
)


def test_flatten_event_markets() -> None:
    """flatten_event_markets extracts all markets from events."""
    events = [
        {"id": "e1", "markets": [{"id": "m1", "conditionId": "c1"}, {"id": "m2", "conditionId": "c2"}]},
        {"id": "e2", "markets": [{"id": "m3", "conditionId": "c3"}]},
        {"id": "e3"},
    ]
    flat = flatten_event_markets(events)
    assert len(flat) == 3
    assert flat[0]["id"] == "m1"
    assert flat[1]["id"] == "m2"
    assert flat[2]["id"] == "m3"


def test_flatten_event_markets_empty() -> None:
    """flatten_event_markets returns [] for empty or no markets."""
    assert flatten_event_markets([]) == []
    assert flatten_event_markets([{"id": "e1"}]) == []
    assert flatten_event_markets([{"id": "e1", "markets": []}]) == []


def test_pick_latest_live_market_prefers_live_over_upcoming() -> None:
    """pick_latest_live_market prefers markets already started (live) over upcoming."""
    now = datetime(2026, 1, 31, 19, 30, 0, tzinfo=timezone.utc)  # 19:30 UTC
    markets = [
        {"id": "upcoming", "endDate": "2026-01-31T21:00:00Z", "eventStartTime": "2026-01-31T20:00:00Z"},
        {"id": "live", "endDate": "2026-01-31T20:00:00Z", "eventStartTime": "2026-01-31T19:00:00Z"},
    ]
    picked = pick_latest_live_market(markets, now=now)
    assert picked is not None
    assert picked["id"] == "live"


def test_pick_latest_live_market_returns_soonest_ending_live() -> None:
    """Among live markets, pick the one with smallest endDate (soonest ending)."""
    now = datetime(2026, 1, 31, 19, 30, 0, tzinfo=timezone.utc)
    markets = [
        {"id": "later", "endDate": "2026-01-31T21:00:00Z", "eventStartTime": "2026-01-31T19:00:00Z"},
        {"id": "soonest", "endDate": "2026-01-31T20:00:00Z", "eventStartTime": "2026-01-31T19:00:00Z"},
    ]
    picked = pick_latest_live_market(markets, now=now)
    assert picked is not None
    assert picked["id"] == "soonest"


def test_pick_latest_live_market_returns_none_when_all_past() -> None:
    """pick_latest_live_market returns None when all markets have ended."""
    now = datetime(2026, 1, 31, 22, 0, 0, tzinfo=timezone.utc)
    markets = [
        {"id": "m1", "endDate": "2026-01-31T20:00:00Z", "eventStartTime": "2026-01-31T19:00:00Z"},
    ]
    picked = pick_latest_live_market(markets, now=now)
    assert picked is None


def test_pick_latest_live_market_returns_upcoming_when_no_live() -> None:
    """When no market is live yet, return soonest upcoming."""
    now = datetime(2026, 1, 31, 18, 0, 0, tzinfo=timezone.utc)
    markets = [
        {"id": "later", "endDate": "2026-01-31T21:00:00Z", "eventStartTime": "2026-01-31T20:00:00Z"},
        {"id": "soonest", "endDate": "2026-01-31T20:00:00Z", "eventStartTime": "2026-01-31T19:00:00Z"},
    ]
    picked = pick_latest_live_market(markets, now=now)
    assert picked is not None
    assert picked["id"] == "soonest"


def test_pick_latest_live_market_accepts_snake_case_dates() -> None:
    """pick_latest_live_market parses end_date and event_start_time (snake_case)."""
    now = datetime(2026, 1, 31, 19, 30, 0, tzinfo=timezone.utc)
    markets = [
        {"id": "m1", "end_date": "2026-01-31T20:00:00Z", "event_start_time": "2026-01-31T19:00:00Z"},
    ]
    picked = pick_latest_live_market(markets, now=now)
    assert picked is not None
    assert picked["id"] == "m1"


def test_parse_updown_market() -> None:
    """parse_updown_market maps Up/Down outcomes to token IDs."""
    raw = {
        "conditionId": "0xabc",
        "slug": "btc-up-down-15m",
        "endDate": "2026-01-31T20:00:00Z",
        "eventStartTime": "2026-01-31T19:00:00Z",
        "outcomes": '["Up", "Down"]',
        "clobTokenIds": ["token_up_123", "token_down_456"],
    }
    m = parse_updown_market(raw, up_label="Up", down_label="Down")
    assert m is not None
    assert m.condition_id == "0xabc"
    assert m.up_token_id == "token_up_123"
    assert m.down_token_id == "token_down_456"
    assert m.end_date == "2026-01-31T20:00:00Z"


def test_parse_updown_market_returns_none_when_missing_outcomes() -> None:
    """parse_updown_market returns None when outcomes or token IDs missing."""
    assert parse_updown_market({"conditionId": "0x"}, up_label="Up", down_label="Down") is None
    assert parse_updown_market({"conditionId": "0x", "outcomes": "[]", "clobTokenIds": []}, up_label="Up", down_label="Down") is None


@pytest.mark.asyncio
async def test_select_btc_15m_updown_market_no_events() -> None:
    """select_btc_15m_updown_market returns None when no events/markets."""
    with patch("app.polymarket.selection_15m.fetch_events_by_series_id", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = []
        market = await select_btc_15m_updown_market(series_id="10192")
    assert market is None
