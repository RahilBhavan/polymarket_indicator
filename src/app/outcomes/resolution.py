"""Resolve market outcome from resolution source (e.g. Binance close at 23:59 UTC or 1h candle)."""

import re
from datetime import datetime, timedelta, timezone
from typing import Literal

import httpx

from app.logging_config import get_logger

logger = get_logger(__name__)

# Binance klines base URL
BINANCE_KLINES = "https://api.binance.com/api/v3/klines"


def is_up_down_market(slug_or_question: str | None, outcomes: list[str] | None = None) -> bool:
    """True if market is Up/Down (1h candle direction). Detect via outcomes or question/slug text."""
    if outcomes is not None and len(outcomes) >= 2:
        if outcomes[0].strip().lower() == "up" and outcomes[1].strip().lower() == "down":
            return True
    text = (slug_or_question or "").strip().lower()
    return "up or down" in text or "up/down" in text or "up-or-down" in text


def _parse_number(group: str) -> float | None:
    """Extract float from captured group (handles commas)."""
    try:
        return float(group.replace(",", ""))
    except ValueError:
        return None


def parse_rule_from_question(slug_or_question: str | None) -> tuple[float | None, float | None]:
    """
    Parse strike rule from market question/slug (e.g. "above $96,500" or "below $97,000").
    Supports: "above $X", "at or above $X", ">= $X", "above or equal $X";
    "below $X", "at or below $X", "<= $X", "below or equal $X".
    Returns (rule_above, rule_below). One will be set, the other None.
    """
    if not slug_or_question:
        return (None, None)
    text = (slug_or_question or "").strip()
    # Above: "above $96,500", "at or above $X", ">= $X", "above or equal $X"
    above_patterns = [
        r"at\s+or\s+above\s+\$?\s*([\d,]+)",
        r">=\s*\$?\s*([\d,]+)",
        r"above\s+or\s+equal\s+\$?\s*([\d,]+)",
        r"above\s+\$?\s*([\d,]+)",
    ]
    for pat in above_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = _parse_number(m.group(1))
            if val is not None:
                return (val, None)
    # Below: "below $97,000", "at or below $X", "<= $X", "below or equal $X"
    below_patterns = [
        r"at\s+or\s+below\s+\$?\s*([\d,]+)",
        r"<=\s*\$?\s*([\d,]+)",
        r"below\s+or\s+equal\s+\$?\s*([\d,]+)",
        r"below\s+\$?\s*([\d,]+)",
    ]
    for pat in below_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = _parse_number(m.group(1))
            if val is not None:
                return (None, val)
    return (None, None)


def resolve_outcome(
    resolution_source: str | None,
    close_price: float | None,
    rule_above: float | None,
    rule_below: float | None,
) -> Literal["YES", "NO"] | None:
    """
    Given resolution source description, close price, and rule (e.g. above 96500),
    return YES if condition met, NO otherwise. Returns None if insufficient data.
    """
    if close_price is None:
        return None
    if rule_above is not None:
        return "YES" if close_price >= rule_above else "NO"
    if rule_below is not None:
        return "YES" if close_price <= rule_below else "NO"
    return None


async def fetch_1h_open_close_binance(candle_start_utc: datetime) -> tuple[float, float] | None:
    """
    Fetch 1h candle open and close from Binance for the given candle start time.
    Returns (open, close) or None on error.
    """
    if candle_start_utc.tzinfo is None:
        candle_start_utc = candle_start_utc.replace(tzinfo=timezone.utc)
    start_ts = int(candle_start_utc.timestamp() * 1000)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                BINANCE_KLINES,
                params={
                    "symbol": "BTCUSDT",
                    "interval": "1h",
                    "startTime": start_ts,
                    "limit": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(
            "binance_1h_fetch_failed",
            candle_start=candle_start_utc.isoformat(),
            error=str(e),
        )
        return None
    if not data or not isinstance(data, list) or len(data) < 1:
        return None
    # Kline: [open_time, open, high, low, close, ...]
    candle = data[0]
    try:
        open_p = float(candle[1])
        close_p = float(candle[4])
    except (IndexError, TypeError, ValueError):
        return None
    return (open_p, close_p)


async def resolve_up_down_1h(end_date_utc: datetime) -> Literal["YES", "NO"] | None:
    """
    Resolve Up/Down 1h market: candle runs [end_date - 1h, end_date]; YES if close >= open else NO.
    """
    candle_start_utc = end_date_utc - timedelta(hours=1)
    if candle_start_utc.tzinfo is None:
        candle_start_utc = candle_start_utc.replace(tzinfo=timezone.utc)
    oc = await fetch_1h_open_close_binance(candle_start_utc)
    if oc is None:
        return None
    open_p, close_p = oc
    return "YES" if close_p >= open_p else "NO"


async def fetch_close_price_binance_utc(end_date_utc: datetime) -> float | None:
    """
    Fetch daily close price from Binance for the day containing end_date_utc.
    Binance 1d klines close at 00:00 UTC; for "23:59 UTC" we use that day's candle close.
    """
    # Candle for 2026-01-30 is 2026-01-30 00:00:00 UTC to 2026-01-31 00:00:00 UTC; close = last price of 30th
    if end_date_utc.tzinfo is None:
        end_date_utc = end_date_utc.replace(tzinfo=timezone.utc)
    day = end_date_utc.date()
    start_ts = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp() * 1000)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                BINANCE_KLINES,
                params={
                    "symbol": "BTCUSDT",
                    "interval": "1d",
                    "startTime": start_ts,
                    "limit": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("binance_close_fetch_failed", end_date=day.isoformat(), error=str(e))
        return None
    if not data or not isinstance(data, list) or len(data) < 1:
        return None
    # Kline: [open_time, open, high, low, close, ...]
    close = data[0][4]
    try:
        return float(close)
    except (TypeError, ValueError):
        return None


def _resolution_source_lower(src: str | None) -> str:
    return (src or "").strip().lower()


def is_binance_resolution(resolution_source: str | None) -> bool:
    """True if resolution source indicates Binance (e.g. 'Binance BTC/USDT close at 23:59 UTC')."""
    return "binance" in _resolution_source_lower(resolution_source)


async def fetch_close_price_from_resolution_source(
    resolution_source: str | None,
    end_date_utc: datetime | None,
) -> float | None:
    """
    Fetch settlement close price from the resolution source (e.g. Binance).
    Do not use a different source (e.g. CoinGecko) when market resolves on Binance.
    """
    if not end_date_utc:
        return None
    if is_binance_resolution(resolution_source):
        return await fetch_close_price_binance_utc(end_date_utc)
    # Add other sources (e.g. Coinbase, Bybit) when needed; never assume.
    logger.debug("resolution_source_unsupported", resolution_source=resolution_source)
    return None


async def resolve_market_outcome(
    resolution_source: str | None,
    end_date_utc: datetime | None,
    slug_or_question: str | None,
    outcomes: list[str] | None = None,
) -> Literal["YES", "NO"] | None:
    """
    For a given market: resolve YES/NO.
    - If Up/Down market (outcomes Up/Down or question contains "Up or Down"): use 1h candle open/close.
    - Else: fetch close from resolution source, parse strike rule from slug/question.
    Returns None if source unsupported or data missing.
    """
    if not end_date_utc:
        return None
    if end_date_utc.tzinfo is None:
        end_date_utc = end_date_utc.replace(tzinfo=timezone.utc)

    if is_up_down_market(slug_or_question, outcomes):
        return await resolve_up_down_1h(end_date_utc)

    rule_above, rule_below = parse_rule_from_question(slug_or_question)
    if rule_above is None and rule_below is None:
        logger.debug("resolve_no_rule", slug_or_question=(slug_or_question or "")[:80])
        return None
    close_price = await fetch_close_price_from_resolution_source(resolution_source, end_date_utc)
    return resolve_outcome(
        resolution_source,
        close_price,
        rule_above,
        rule_below,
    )
