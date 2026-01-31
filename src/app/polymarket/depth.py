"""Compute max safe size (USD) from order book given slippage limit."""

from app.config import get_settings
from app.polymarket.models import OrderBook


def max_safe_size_usd(book: OrderBook, side: str = "ask") -> float:
    """
    Max size (in USD) such that volume-weighted slippage stays <= SLIPPAGE_LIMIT.
    For buying YES we consume asks (side=ask). Size is in shares; price * size = USD.
    We walk the book until cumulative slippage vs best price exceeds limit.
    """
    settings = get_settings()
    limit = settings.slippage_limit
    if side == "ask":
        levels = book.asks
        best = book.best_ask
    else:
        levels = book.bids
        best = book.best_bid
    if not levels or best is None or best <= 0:
        return 0.0
    cumulative_usd = 0.0
    cumulative_shares = 0.0
    for level in levels:
        price = level.price
        size = level.size
        # Slippage vs best: (avg_price - best) / best for asks
        new_shares = cumulative_shares + size
        new_usd = cumulative_usd + price * size
        avg_price = new_usd / new_shares if new_shares > 0 else price
        if side == "ask":
            slippage = (avg_price - best) / best if best else 0
        else:
            slippage = (best - avg_price) / best if best else 0
        if slippage > limit:
            # Stop before this level; interpolate or use previous
            break
        cumulative_usd = new_usd
        cumulative_shares = new_shares
    return round(cumulative_usd, 2)
