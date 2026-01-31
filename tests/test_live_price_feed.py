"""Tests for live BTC/USD price feed (Chainlink HTTP fallback, priority)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.live_prices.chainlink_polygon_http import (
    ChainlinkResult,
    _decode_latest_round_data,
)
from app.live_prices.price_feed import get_last_price_async, PriceTick


def test_decode_latest_round_data() -> None:
    """_decode_latest_round_data decodes ABI-encoded latestRoundData return."""
    # Minimal 5 * 32 bytes: roundId, answer (int256), startedAt, updatedAt, answeredInRound
    # answer = 97500 * 1e8 = 9750000000000
    answer_val = 9750000000000
    updated_val = 1738342800  # timestamp
    # eth_abi encodes int256; for positive same as uint256
    raw = (
        b"\x00" * 31
        + b"\x01"  # roundId 1
        + (answer_val).to_bytes(32, "big")  # answer
        + (0).to_bytes(32, "big")  # startedAt
        + (updated_val).to_bytes(32, "big")  # updatedAt
        + b"\x00" * 31
        + b"\x01"  # answeredInRound 1
    )
    result_hex = "0x" + raw.hex()
    decoded = _decode_latest_round_data(result_hex)
    assert decoded is not None
    answer, updated_at = decoded
    assert answer == answer_val
    assert updated_at == updated_val


def test_decode_latest_round_data_invalid() -> None:
    """_decode_latest_round_data returns None for invalid input."""
    assert _decode_latest_round_data("") is None
    assert _decode_latest_round_data("0x") is None
    assert _decode_latest_round_data("0x1234") is None  # too short


@pytest.mark.asyncio
async def test_get_last_price_async_prefers_polymarket_ws() -> None:
    """get_last_price_async returns Polymarket WS tick when it has price."""
    from app.live_prices.polymarket_chainlink_ws import PolymarketWsTick

    with patch("app.live_prices.price_feed.polymarket_ws_get_last") as mock_pm:
        mock_pm.return_value = PolymarketWsTick(
            price=97200.0,
            updated_at_ms=1738342800000,
            source="polymarket_ws",
        )
        tick = await get_last_price_async()
    assert tick.price == 97200.0
    assert tick.source == "polymarket_ws"


@pytest.mark.asyncio
async def test_get_last_price_async_falls_back_to_http() -> None:
    """get_last_price_async returns Chainlink HTTP result when no WS data."""
    with patch(
        "app.live_prices.price_feed.fetch_chainlink_btc_usd", new_callable=AsyncMock
    ) as mock_http:
        mock_http.return_value = ChainlinkResult(
            price=97500.0,
            updated_at_ms=1738342800000,
            source="chainlink_http",
        )
        tick = await get_last_price_async()
    assert isinstance(tick, PriceTick)
    assert tick.price == 97500.0
    assert tick.source == "chainlink_http"


@pytest.mark.asyncio
async def test_get_last_price_async_returns_tick_when_http_fails() -> None:
    """get_last_price_async returns PriceTick with None price when all sources fail."""
    with patch(
        "app.live_prices.price_feed.fetch_chainlink_btc_usd", new_callable=AsyncMock
    ) as mock_http:
        mock_http.return_value = ChainlinkResult(
            price=None, updated_at_ms=None, source="chainlink_http"
        )
        tick = await get_last_price_async()
    assert tick.price is None
    assert tick.source == "chainlink_http"
