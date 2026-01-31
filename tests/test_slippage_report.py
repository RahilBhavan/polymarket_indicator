"""Slippage report: snapshot_to_order_book, VWAP and slippage_bps with synthetic OB."""

from app.analytics.slippage_audit import slippage_bps, vwap_for_size_usd
from app.polymarket.models import OrderBook, OrderBookLevel


def test_vwap_for_size_usd_ask() -> None:
    """VWAP for $100 on asks: two levels 0.6 ($50) and 0.65 ($60)."""
    book = OrderBook(
        asks=[
            OrderBookLevel(price=0.6, size=100),
            OrderBookLevel(price=0.65, size=100),
        ],
        bids=[],
    )
    vwap = vwap_for_size_usd(book, "ask", 100.0)
    assert vwap is not None
    # 100 USD at 0.6 = 166.67 shares, so we take full first level (100 shares = $60) + 40/0.65 from second
    # Actually level size is in shares: 100 shares at 0.6 = $60. So $100 fills 100 shares at 0.6 = $60, then 40/0.65 ≈ 61.5 shares. Total cost 60+40=100, total shares 100+61.5=161.5, vwap = 100/161.5 ≈ 0.619
    assert 0.5 < vwap < 0.7


def test_slippage_bps_positive() -> None:
    """VWAP > quoted => positive slippage (bps)."""
    assert slippage_bps(0.60, 0.62) > 0
    assert abs(slippage_bps(0.60, 0.62) - (0.02 / 0.60 * 10000)) < 1


def test_slippage_bps_zero_quoted_returns_zero() -> None:
    """Zero quoted price returns 0 bps."""
    assert slippage_bps(0.0, 0.62) == 0.0
