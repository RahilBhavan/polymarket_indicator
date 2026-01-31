"""Orchestrator: best available BTC/USD price (Polymarket WS -> Chainlink WS -> Chainlink HTTP)."""

from dataclasses import dataclass

from app.live_prices.chainlink_polygon_http import (
    ChainlinkResult,
    fetch_chainlink_btc_usd,
)
from app.live_prices.chainlink_polygon_ws import get_last as chainlink_ws_get_last
from app.live_prices.polymarket_chainlink_ws import get_last as polymarket_ws_get_last


@dataclass
class PriceTick:
    """Best available price with timestamp and source."""

    price: float | None
    updated_at_ms: int | None
    source: str


async def get_last_price_async() -> PriceTick:
    """
    Return best available BTC/USD price.
    Priority: Polymarket WS -> Chainlink WSS -> Chainlink HTTP.
    Does not start WS; if no WS data, falls back to HTTP fetch.
    """
    pm = polymarket_ws_get_last()
    if pm.price is not None:
        return PriceTick(
            price=pm.price,
            updated_at_ms=pm.updated_at_ms,
            source=pm.source,
        )
    cl_ws = chainlink_ws_get_last()
    if cl_ws.price is not None:
        return PriceTick(
            price=cl_ws.price,
            updated_at_ms=cl_ws.updated_at_ms,
            source=cl_ws.source,
        )
    result: ChainlinkResult = await fetch_chainlink_btc_usd()
    return PriceTick(
        price=result.price,
        updated_at_ms=result.updated_at_ms,
        source=result.source,
    )
