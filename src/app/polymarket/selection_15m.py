"""Select active BTC 15m Up/Down market by series ID (Gamma events)."""

import asyncio
from datetime import datetime, timezone

from app.polymarket.client import (
    fetch_clob_price,
    fetch_events_by_series_id,
    fetch_order_book,
    parse_updown_market,
)
from app.polymarket.depth import max_safe_size_usd
from app.polymarket.models import UpDownMarket, UpDownQuote
from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


def flatten_event_markets(events: list[dict]) -> list[dict]:
    """Extract all markets from events. Each event may have a 'markets' list."""
    out: list[dict] = []
    for e in events or []:
        markets = e.get("markets") or []
        for m in markets:
            out.append(m)
    return out


def _safe_time_ms(value: str | None) -> int | None:
    """Parse ISO date string to Unix ms; None if missing or invalid."""
    if not value:
        return None
    try:
        # Handle Z suffix
        s = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return None


def pick_latest_live_market(
    markets: list[dict],
    now: datetime | None = None,
) -> dict | None:
    """
    Choose the market with smallest endDate that is still in the future.
    Prefer markets already started (eventStartTime <= now); if none live, pick soonest upcoming.
    """
    if not markets:
        return None
    now = now or datetime.now(timezone.utc)
    now_ms = int(now.timestamp() * 1000)

    enriched: list[tuple[dict, int | None, int | None]] = []
    for m in markets:
        end_ms = _safe_time_ms(m.get("endDate") or m.get("end_date"))
        start_ms = _safe_time_ms(
            m.get("eventStartTime") or m.get("event_start_time") or m.get("startTime") or m.get("startDate")
        )
        if end_ms is None:
            continue
        enriched.append((m, end_ms, start_ms))

    # Live: started and not ended
    live = [
        (m, end_ms, start_ms)
        for m, end_ms, start_ms in enriched
        if (start_ms is None or start_ms <= now_ms) and now_ms < end_ms
    ]
    if live:
        live.sort(key=lambda x: x[1])  # by end_ms ascending
        return live[0][0]

    # Upcoming: not yet started
    upcoming = [(m, end_ms, start_ms) for m, end_ms, start_ms in enriched if now_ms < end_ms]
    if upcoming:
        upcoming.sort(key=lambda x: x[1])
        return upcoming[0][0]

    return None


async def select_btc_15m_updown_market(
    series_id: str | None = None,
    market_slug: str | None = None,
    up_label: str = "Up",
    down_label: str = "Down",
) -> UpDownMarket | None:
    """
    Select the current BTC 15m Up/Down market.
    If market_slug is set, fetch that market by slug and parse (no series lookup).
    Otherwise fetch events by series_id, flatten markets, pick latest live, parse as UpDownMarket.
    """
    settings = get_settings()
    series_id = series_id or settings.polymarket_series_id_15m
    up_label = up_label or settings.polymarket_up_label
    down_label = down_label or settings.polymarket_down_label

    if market_slug:
        from app.polymarket.client import fetch_markets

        raw_list = await fetch_markets(closed=False, limit=10, slug=market_slug)
        if not raw_list:
            return None
        raw = raw_list[0] if isinstance(raw_list[0], dict) else raw_list
        return parse_updown_market(raw, up_label=up_label, down_label=down_label)

    events = await fetch_events_by_series_id(series_id=series_id, limit=25, active=True, closed=False)
    flat = flatten_event_markets(events)
    picked = pick_latest_live_market(flat)
    if not picked:
        logger.info("select_15m_no_market", series_id=series_id)
        return None
    parsed = parse_updown_market(picked, up_label=up_label, down_label=down_label)
    if parsed:
        logger.info("select_15m_ok", condition_id=parsed.condition_id, slug=parsed.slug)
    return parsed


async def build_updown_quote(market: UpDownMarket) -> UpDownQuote | None:
    """
    Fetch CLOB prices and order books for Up/Down tokens; build UpDownQuote.
    Normalizes market_up_norm = up_price / (up_price + down_price).
    """
    try:
        up_price_raw, down_price_raw, book_up, book_down = await asyncio.gather(
            fetch_clob_price(market.up_token_id, "buy"),
            fetch_clob_price(market.down_token_id, "buy"),
            fetch_order_book(market.up_token_id),
            fetch_order_book(market.down_token_id),
        )
    except Exception as e:
        logger.warning("build_updown_quote_failed", error=str(e))
        return None
    up_price = up_price_raw if up_price_raw is not None else 0.0
    down_price = down_price_raw if down_price_raw is not None else 0.0
    total = up_price + down_price
    if total <= 0:
        market_up_norm = 0.5
        market_down_norm = 0.5
    else:
        market_up_norm = up_price / total
        market_down_norm = down_price / total
    max_safe_up = max_safe_size_usd(book_up, side="ask") if book_up else 0.0
    max_safe_down = max_safe_size_usd(book_down, side="ask") if book_down else 0.0
    spread_up = book_up.spread if book_up else None
    spread_down = book_down.spread if book_down else None
    liquidity_num = market.raw.get("liquidityNum") or market.raw.get("liquidity")
    liquidity_num = float(liquidity_num) if liquidity_num is not None else None
    return UpDownQuote(
        up_buy_price=up_price,
        down_buy_price=down_price,
        market_up_norm=market_up_norm,
        market_down_norm=market_down_norm,
        max_safe_up_usd=max_safe_up,
        max_safe_down_usd=max_safe_down,
        spread_up=spread_up,
        spread_down=spread_down,
        liquidity_num=liquidity_num,
    )
