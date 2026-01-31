"""Select active daily or hourly BTC market (prefer next upcoming hourly Up/Down)."""

import re
from datetime import date, datetime, timezone

from app.polymarket.client import fetch_markets, parse_market
from app.polymarket.models import Market

# Slug patterns for BTC daily (e.g. "bitcoin-above-96500-on-january-30" or "btc-daily-...")
BTC_DAILY_PATTERNS = (
    re.compile(r"bitcoin.*(?:above|below|close|daily)", re.I),
    re.compile(r"btc.*(?:above|below|close|daily)", re.I),
    re.compile(r"daily.*bitcoin", re.I),
)

# Slug patterns for BTC hourly Up/Down (e.g. "bitcoin-up-or-down-january-31-2pm-et")
BTC_UP_DOWN_HOURLY_PATTERNS = (
    re.compile(r"bitcoin.*up.*down", re.I),
    re.compile(r"btc.*up.*down", re.I),
)


def _is_btc_daily_slug(slug: str | None) -> bool:
    if not slug:
        return False
    return any(p.search(slug) for p in BTC_DAILY_PATTERNS)


def _is_btc_up_down_hourly_slug(slug: str | None) -> bool:
    if not slug:
        return False
    return any(p.search(slug) for p in BTC_UP_DOWN_HOURLY_PATTERNS)


def is_btc_up_down_hourly_market(market: Market) -> bool:
    """True if market is an hourly BTC Up/Down market (for fetcher/weight selection)."""
    return _is_btc_up_down_hourly_slug(market.slug)


def _is_active_and_open(m: Market) -> bool:
    """Market is active, not closed, and has order book."""
    if m.closed or not m.active:
        return False
    if m.enable_order_book is False:
        return False
    return True


def _end_date_after(m: Market, d: date) -> bool:
    """Market end date is on or after d (UTC)."""
    if not m.end_date:
        return True
    try:
        # ISO format e.g. 2026-01-30T23:59:59Z
        end = datetime.fromisoformat(m.end_date.replace("Z", "+00:00"))
        return end.date() >= d
    except Exception:
        return True


async def select_btc_daily_market(for_date: date | None = None) -> Market | None:
    """
    Select the active daily BTC market for the given date (default: today UTC).
    Returns first matching market: BTC daily slug, active, open, end_date >= for_date.
    """
    for_date = for_date or date.today()
    end_min = for_date.isoformat() + "T00:00:00Z"
    raw = await fetch_markets(closed=False, limit=200, end_date_min=end_min)
    candidates: list[Market] = []
    for r in raw:
        m = parse_market(r)
        if not m or not m.condition_id:
            continue
        if not _is_btc_daily_slug(m.slug):
            continue
        if not _is_active_and_open(m):
            continue
        if not _end_date_after(m, for_date):
            continue
        candidates.append(m)
    # Prefer by end_date closest to for_date end-of-day
    if not candidates:
        return None
    candidates.sort(key=lambda m: m.end_date or "", reverse=False)
    return candidates[0]


def _parse_event_start_utc(m: Market) -> datetime | None:
    """Parse event_start_time to datetime UTC; None if missing or invalid."""
    raw = m.event_start_time
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


async def select_btc_up_down_hourly_market(now_utc: datetime | None = None) -> Market | None:
    """
    Select the next upcoming hourly BTC Up/Down market.
    Returns first matching: slug matches Up/Down, active, open, event_start_time in the future.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    end_min = now_utc.date().isoformat() + "T00:00:00Z"
    raw = await fetch_markets(closed=False, limit=200, end_date_min=end_min)
    candidates: list[Market] = []
    for r in raw:
        m = parse_market(r)
        if not m or not m.condition_id:
            continue
        if not _is_btc_up_down_hourly_slug(m.slug):
            continue
        if not _is_active_and_open(m):
            continue
        event_start = _parse_event_start_utc(m)
        if event_start is None or event_start <= now_utc:
            continue
        candidates.append(m)
    if not candidates:
        return None
    candidates.sort(
        key=lambda m: _parse_event_start_utc(m) or datetime.max.replace(tzinfo=timezone.utc)
    )
    return candidates[0]


async def select_btc_market(now_utc: datetime | None = None) -> Market | None:
    """
    Prefer next upcoming hourly Up/Down market; fall back to daily BTC market.
    """
    market = await select_btc_up_down_hourly_market(now_utc)
    if market is not None:
        return market
    return await select_btc_daily_market(now_utc.date() if now_utc else None)
