"""Phase 2: order book parsing (CLOB response) and max_safe_size_usd."""

import pytest
from app.polymarket.client import parse_order_book, parse_market
from app.polymarket.depth import max_safe_size_usd
from app.polymarket.models import OrderBook, OrderBookLevel


def test_parse_order_book_clob_response() -> None:
    """Order book parsing from CLOB-shaped dict: best bid/ask, spread, implied_prob_yes."""
    data = {
        "bids": [{"price": "0.55", "size": "100"}, {"price": "0.54", "size": "200"}],
        "asks": [{"price": "0.60", "size": "150"}, {"price": "0.62", "size": "250"}],
    }
    book = parse_order_book(data)
    assert book.best_bid == 0.55
    assert book.best_ask == 0.60
    assert book.spread == pytest.approx(0.05)
    assert book.implied_prob_yes == 0.60
    assert len(book.bids) == 2
    assert len(book.asks) == 2
    assert book.bids[0].price > book.bids[1].price
    assert book.asks[0].price < book.asks[1].price


def test_parse_order_book_empty() -> None:
    """Empty CLOB response yields empty book, no best bid/ask."""
    book = parse_order_book({"bids": [], "asks": []})
    assert book.best_bid is None
    assert book.best_ask is None
    assert book.spread is None
    assert book.implied_prob_yes is None


def test_parse_market_clob_token_ids_list() -> None:
    """Gamma can return clobTokenIds as list [yes_id, no_id]; we take first (YES)."""
    raw = {
        "id": "1",
        "conditionId": "0xabc",
        "question": "BTC above 96k?",
        "slug": "bitcoin-above-96000",
        "clobTokenIds": ["token_yes_123", "token_no_456"],
    }
    m = parse_market(raw)
    assert m is not None
    assert m.condition_id == "0xabc"
    assert m.clob_token_ids == "token_yes_123"


def test_max_safe_size_usd_asks() -> None:
    """Walk asks until slippage exceeds limit."""
    book = OrderBook(
        bids=[],
        asks=[
            OrderBookLevel(price=0.60, size=100),
            OrderBookLevel(price=0.62, size=200),
            OrderBookLevel(price=0.65, size=300),
        ],
        best_bid=None,
        best_ask=0.60,
    )
    # At 0.60 only: 100 shares = 60 USD, slippage 0.
    # Adding 0.62 level: (60+124)/300 = 0.6133, slippage (0.6133-0.60)/0.60 ≈ 2.2% > 1%
    # So max safe = 60 USD (first level only) when SLIPPAGE_LIMIT=0.01
    size = max_safe_size_usd(book, side="ask")
    assert size == 60.0


def test_max_safe_size_usd_empty_book() -> None:
    """Empty book returns 0."""
    book = OrderBook(bids=[], asks=[], best_bid=None, best_ask=None)
    assert max_safe_size_usd(book, side="ask") == 0.0
