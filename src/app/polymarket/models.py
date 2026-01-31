"""Pydantic models for Polymarket market and order book."""

import json
from typing import Any

from pydantic import BaseModel, Field


class Market(BaseModel):
    """Single market from Gamma API (daily or hourly Up/Down)."""

    id: str
    question: str | None = None
    condition_id: str = Field(..., alias="conditionId")
    slug: str | None = None
    resolution_source: str | None = Field(None, alias="resolutionSource")
    end_date: str | None = Field(None, alias="endDate")
    closed: bool | None = None
    active: bool | None = None
    enable_order_book: bool | None = Field(None, alias="enableOrderBook")
    best_bid: float | None = Field(None, alias="bestBid")
    best_ask: float | None = Field(None, alias="bestAsk")
    clob_token_ids: str | None = Field(None, alias="clobTokenIds")
    liquidity_num: float | None = Field(None, alias="liquidityNum")
    outcomes_raw: str | None = Field(None, alias="outcomes")
    event_start_time: str | None = Field(None, alias="eventStartTime")

    model_config = {"populate_by_name": True, "extra": "ignore"}

    @property
    def outcomes_list(self) -> list[str]:
        """Parse outcomes_raw JSON string to list; empty if missing or invalid."""
        if not self.outcomes_raw:
            return []
        try:
            parsed: Any = json.loads(self.outcomes_raw)
            if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                return parsed
            return []
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def yes_label(self) -> str | None:
        """First outcome label (e.g. Up); None if not binary."""
        lst = self.outcomes_list
        return lst[0] if len(lst) >= 1 else None

    @property
    def no_label(self) -> str | None:
        """Second outcome label (e.g. Down); None if not binary."""
        lst = self.outcomes_list
        return lst[1] if len(lst) >= 2 else None


class OrderBookLevel(BaseModel):
    """Single price level (price, size)."""

    price: float
    size: float  # in shares or USD depending on API


class OrderBook(BaseModel):
    """Order book: bids and asks with levels."""

    bids: list[OrderBookLevel] = Field(default_factory=list)
    asks: list[OrderBookLevel] = Field(default_factory=list)
    best_bid: float | None = None
    best_ask: float | None = None

    @property
    def spread(self) -> float | None:
        """Best ask - best bid."""
        if self.best_bid is not None and self.best_ask is not None:
            return round(self.best_ask - self.best_bid, 4)
        return None

    @property
    def implied_prob_yes(self) -> float | None:
        """Market-implied probability for YES (best ask for binary)."""
        return self.best_ask


class MarketQuote(BaseModel):
    """Quote summary: best bid/ask, spread, implied prob, max safe size."""

    best_bid: float
    best_ask: float
    spread: float
    implied_prob_yes: float
    max_safe_size_usd: float = Field(..., description="Max size before slippage exceeds limit")


class UpDownMarket(BaseModel):
    """BTC 15m Up/Down market: both outcome token IDs, end/start times, base payload."""

    condition_id: str
    slug: str | None = None
    question: str | None = None
    resolution_source: str | None = None
    end_date: str | None = None
    event_start_time: str | None = None
    up_token_id: str
    down_token_id: str
    raw: dict[str, Any] = Field(default_factory=dict, description="Original Gamma market payload")


class UpDownQuote(BaseModel):
    """Quote for Up/Down market: prices, normalized probs, max safe sizes per side."""

    up_buy_price: float
    down_buy_price: float
    market_up_norm: float
    market_down_norm: float
    max_safe_up_usd: float
    max_safe_down_usd: float
    spread_up: float | None = None
    spread_down: float | None = None
    liquidity_num: float | None = None
