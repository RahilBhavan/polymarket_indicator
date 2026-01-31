"""Async client for Gamma API (markets) and CLOB (order book)."""

import json
from typing import Any, Literal

import httpx
from app.config import get_settings
from app.logging_config import get_logger
from app.polymarket.models import Market, OrderBook, OrderBookLevel, UpDownMarket

logger = get_logger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"


def _polymarket_headers() -> dict[str, str]:
    """Optional auth header when POLYMARKET_API_KEY is set (Bearer token)."""
    key = get_settings().polymarket_api_key
    if not key or not key.strip():
        return {}
    return {"Authorization": f"Bearer {key.strip()}"}


async def fetch_markets(
    closed: bool = False,
    limit: int = 100,
    slug: str | None = None,
    end_date_min: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch markets from Gamma API. Filter by query params."""
    params: dict[str, Any] = {"closed": str(closed).lower(), "limit": limit}
    if slug:
        params["slug"] = slug
    if end_date_min:
        params["end_date_min"] = end_date_min
    headers = _polymarket_headers()
    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        resp = await client.get(f"{GAMMA_BASE}/markets", params=params)
        resp.raise_for_status()
        data = resp.json()
    return data if isinstance(data, list) else []


def _normalize_clob_token_ids(raw: dict[str, Any]) -> str | None:
    """Gamma returns clobTokenIds as list [yes_id, no_id] or sometimes string. Return YES token (first)."""
    val = raw.get("clobTokenIds")
    if val is None:
        return None
    if isinstance(val, list):
        return val[0] if val else None
    if isinstance(val, str):
        part = val.split(",")[0].strip() if val else None
        return part or None
    return None


def parse_market(raw: dict[str, Any]) -> Market | None:
    """Parse one market; return None if missing required fields."""
    try:
        clob_ids = _normalize_clob_token_ids(raw)
        return Market(
            id=str(raw.get("id", "")),
            conditionId=raw.get("conditionId") or "",
            question=raw.get("question"),
            slug=raw.get("slug"),
            resolutionSource=raw.get("resolutionSource"),
            endDate=raw.get("endDate"),
            closed=raw.get("closed"),
            active=raw.get("active"),
            enableOrderBook=raw.get("enableOrderBook"),
            bestBid=raw.get("bestBid"),
            bestAsk=raw.get("bestAsk"),
            clobTokenIds=clob_ids,
            liquidityNum=raw.get("liquidityNum"),
            outcomes_raw=raw.get("outcomes"),
            event_start_time=raw.get("eventStartTime"),
        )
    except Exception as e:
        logger.warning("parse_market_skip", raw_id=raw.get("id"), error=str(e))
        return None


def parse_order_book(data: dict[str, Any]) -> OrderBook:
    """
    Parse CLOB response dict into OrderBook. Bids sorted desc, asks asc.
    Handles price/size as strings or numbers.
    """
    raw_bids = data.get("bids") or []
    raw_asks = data.get("asks") or []
    bids = sorted(
        [
            OrderBookLevel(price=float(b.get("price", 0)), size=float(b.get("size", 0)))
            for b in raw_bids
        ],
        key=lambda x: x.price,
        reverse=True,
    )
    asks = sorted(
        [
            OrderBookLevel(price=float(a.get("price", 0)), size=float(a.get("size", 0)))
            for a in raw_asks
        ],
        key=lambda x: x.price,
    )
    best_bid = bids[0].price if bids else None
    best_ask = asks[0].price if asks else None
    return OrderBook(bids=bids, asks=asks, best_bid=best_bid, best_ask=best_ask)


async def fetch_order_book(token_id: str) -> OrderBook:
    """
    Fetch order book for one token (YES side) from CLOB.
    GET /book?token_id=...
    """
    headers = _polymarket_headers()
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        resp = await client.get(f"{CLOB_BASE}/book", params={"token_id": token_id})
        resp.raise_for_status()
        data = resp.json()
    return parse_order_book(data)


async def fetch_events_by_series_id(
    series_id: str,
    limit: int = 25,
    active: bool = True,
    closed: bool = False,
) -> list[dict[str, Any]]:
    """Fetch events from Gamma API by series_id. Used for BTC 15m series."""
    params: dict[str, Any] = {
        "series_id": series_id,
        "active": str(active).lower(),
        "closed": str(closed).lower(),
        "limit": limit,
    }
    headers = _polymarket_headers()
    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        resp = await client.get(f"{GAMMA_BASE}/events", params=params)
        resp.raise_for_status()
        data = resp.json()
    return data if isinstance(data, list) else []


def _parse_outcomes_and_token_ids(raw: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (outcomes list, clobTokenIds list) from market payload."""
    outcomes_raw = raw.get("outcomes")
    if isinstance(outcomes_raw, str):
        try:
            outcomes = json.loads(outcomes_raw)
        except (TypeError, ValueError):
            outcomes = []
    elif isinstance(outcomes_raw, list):
        outcomes = [str(x) for x in outcomes_raw]
    else:
        outcomes = []

    ids_raw = raw.get("clobTokenIds")
    if isinstance(ids_raw, list):
        ids = [str(x).strip() for x in ids_raw if x is not None]
    elif isinstance(ids_raw, str):
        ids = [s.strip() for s in ids_raw.split(",") if s.strip()]
    else:
        ids = []
    return outcomes, ids


def parse_updown_market(
    raw: dict[str, Any],
    up_label: str = "Up",
    down_label: str = "Down",
) -> UpDownMarket | None:
    """
    Parse a Gamma market (from event markets) into UpDownMarket.
    Maps outcomes to token IDs by label (Up -> up_token_id, Down -> down_token_id).
    """
    outcomes, token_ids = _parse_outcomes_and_token_ids(raw)
    if len(outcomes) < 2 or len(token_ids) < 2:
        logger.warning(
            "parse_updown_skip", reason="need two outcomes and two token ids", raw_id=raw.get("id")
        )
        return None
    up_label_lower = up_label.strip().lower()
    down_label_lower = down_label.strip().lower()
    up_index = next(
        (i for i, o in enumerate(outcomes) if o.strip().lower() == up_label_lower), None
    )
    down_index = next(
        (i for i, o in enumerate(outcomes) if o.strip().lower() == down_label_lower), None
    )
    if up_index is None or down_index is None:
        logger.warning("parse_updown_skip", reason="up/down labels not found", outcomes=outcomes)
        return None
    if up_index >= len(token_ids) or down_index >= len(token_ids):
        return None
    condition_id = raw.get("conditionId") or raw.get("condition_id") or ""
    if not condition_id:
        return None
    return UpDownMarket(
        condition_id=condition_id,
        slug=raw.get("slug"),
        question=raw.get("question"),
        resolution_source=raw.get("resolutionSource") or raw.get("resolution_source"),
        end_date=raw.get("endDate") or raw.get("end_date"),
        event_start_time=raw.get("eventStartTime") or raw.get("event_start_time"),
        up_token_id=token_ids[up_index],
        down_token_id=token_ids[down_index],
        raw=raw,
    )


async def fetch_clob_price(token_id: str, side: Literal["buy", "sell"]) -> float | None:
    """Fetch CLOB price for one token. GET /price?token_id=...&side=buy|sell."""
    headers = _polymarket_headers()
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        resp = await client.get(f"{CLOB_BASE}/price", params={"token_id": token_id, "side": side})
        resp.raise_for_status()
        data = resp.json()
    price = data.get("price")
    if price is None:
        return None
    try:
        return float(price)
    except (TypeError, ValueError):
        return None
