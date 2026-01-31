"""Slippage audit: compare quoted price vs VWAP for recommended size (paper mode)."""

from app.polymarket.models import OrderBook


def vwap_for_size_usd(book: OrderBook, side: str, size_usd: float) -> float | None:
    """
    Volume-weighted average price to fill size_usd (in USD) on asks (side=ask) or bids.
    Returns None if insufficient liquidity.
    """
    levels = book.asks if side == "ask" else book.bids
    remaining_usd = size_usd
    total_cost = 0.0
    total_shares = 0.0
    for level in levels:
        price = level.price
        size_shares = level.size
        level_usd = price * size_shares
        if remaining_usd <= 0:
            break
        if level_usd >= remaining_usd:
            shares_take = remaining_usd / price
            total_cost += remaining_usd
            total_shares += shares_take
            remaining_usd = 0
            break
        total_cost += level_usd
        total_shares += size_shares
        remaining_usd -= level_usd
    if remaining_usd > 0.01:
        return None
    if total_shares <= 0:
        return None
    return total_cost / total_shares


def slippage_bps(quoted_price: float, vwap: float) -> float:
    """Slippage in basis points: (vwap - quoted) / quoted * 10000 for ask."""
    if quoted_price <= 0:
        return 0.0
    return (vwap - quoted_price) / quoted_price * 10000
