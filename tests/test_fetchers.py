"""Fetchers: registry runs all and returns FeatureSnapshot."""

from unittest.mock import MagicMock, patch

import pytest

from app.fetchers.base import FetcherResult, reset_circuits, with_retry
from app.fetchers.bounds import check_bounds, out_of_range_result
from app.fetchers.dxy import DxyFetcher
from app.fetchers.etf_flows import EtfFlowsFetcher
from app.fetchers.exchange_netflow import ExchangeNetflowFetcher
from app.fetchers.fear_greed import FearGreedFetcher
from app.fetchers.funding import FundingFetcher
from app.fetchers.macro import MacroFetcher
from app.fetchers.price_ma import PriceMaFetcher
from app.fetchers.registry import FeatureSnapshot, get_all_fetchers, run_all_fetchers


def test_get_all_fetchers() -> None:
    """Registry returns list of fetchers."""
    fetchers = get_all_fetchers()
    assert len(fetchers) >= 5
    assert all(hasattr(f, "source_id") and hasattr(f, "fetch") for f in fetchers)


@pytest.mark.asyncio
async def test_run_all_fetchers_returns_snapshot() -> None:
    """run_all_fetchers returns FeatureSnapshot with results (may have errors)."""
    snapshot = await run_all_fetchers()
    assert isinstance(snapshot, FeatureSnapshot)
    assert isinstance(snapshot.results, list)
    assert len(snapshot.results) == len(get_all_fetchers())
    assert all(isinstance(r, FetcherResult) for r in snapshot.results)


def test_feature_snapshot_to_rows() -> None:
    """to_rows produces list of dicts for DB."""
    snapshot = FeatureSnapshot(
        results=[
            FetcherResult("a", "1", 0.5, False),
            FetcherResult("b", "2", None, True),
        ],
        timestamp="2026-01-30T12:00:00Z",
    )
    rows = snapshot.to_rows()
    assert len(rows) == 2
    assert rows[0]["source_id"] == "a"
    assert rows[0]["raw_value"] == "1"
    assert rows[0]["normalized_score"] == 0.5
    assert rows[1]["stale"] is True


# --- normalize() unit tests ---


def test_normalize_etf_flows() -> None:
    """ETF flows: >200 -> +2, >0 -> +1, <0 -> -1, <-200 -> -2."""
    f = EtfFlowsFetcher()
    assert f.normalize(250) == 2.0
    assert f.normalize(100) == 1.0
    assert f.normalize(0) == 1.0
    assert f.normalize(-100) == -1.0
    assert f.normalize(-250) == -2.0
    assert f.normalize(None) is None


def test_normalize_funding() -> None:
    """Funding: negative -> +1, neutral -> 0, high positive -> -1."""
    f = FundingFetcher()
    assert f.normalize(-0.0002) == 1.0
    assert f.normalize(0.0001) == 0.0
    assert f.normalize(0.001) == -1.0
    assert f.normalize(None) is None


def test_normalize_dxy() -> None:
    """DXY 5d trend %: down >1% -> +2, down -> +1, up -> -1, up >1% -> -2."""
    f = DxyFetcher()
    assert f.normalize(-2.0) == 2.0
    assert f.normalize(-0.5) == 1.0
    assert f.normalize(0.5) == -1.0
    assert f.normalize(2.0) == -2.0
    assert f.normalize(None) is None


def test_normalize_fear_greed() -> None:
    """Fear & Greed: <25 -> +2, <40 -> +1, >60 -> -1, >80 -> -2."""
    f = FearGreedFetcher()
    assert f.normalize(20) == 2.0
    assert f.normalize(30) == 1.0
    assert f.normalize(50) == 0.0
    assert f.normalize(70) == -1.0
    assert f.normalize(90) == -2.0
    assert f.normalize(None) is None


def test_normalize_price_ma() -> None:
    """Price vs MA %: >5% -> +1, >0 -> +0.5, <0 -> -0.5, <-5% -> -1."""
    f = PriceMaFetcher()
    assert f.normalize(6) == 1.0
    assert f.normalize(2) == 0.5
    assert f.normalize(-2) == -0.5
    assert f.normalize(-6) == -1.0
    assert f.normalize(None) is None


def test_normalize_exchange_netflow() -> None:
    """Exchange netflow: outflow >5k -> +2, inflow >5k -> -2."""
    f = ExchangeNetflowFetcher()
    assert f.normalize(-6000) == 2.0
    assert f.normalize(-1000) == 1.0
    assert f.normalize(1000) == -1.0
    assert f.normalize(6000) == -2.0
    assert f.normalize(None) is None


def test_normalize_macro() -> None:
    """Macro: raw float passed through (no_event 0.5, event -1)."""
    f = MacroFetcher()
    assert f.normalize(0.5) == 0.5
    assert f.normalize(-1.0) == -1.0
    assert f.normalize(None) is None


# --- sanity bounds ---


def test_check_bounds_in_range() -> None:
    """check_bounds returns True for values within defined bounds."""
    assert check_bounds("fear_greed", 50.0) is True
    assert check_bounds("fear_greed", 0.0) is True
    assert check_bounds("fear_greed", 100.0) is True
    assert check_bounds("funding", 0.0001) is True
    assert check_bounds("dxy", 5.0) is True
    assert check_bounds("price_ma", 10.0) is True
    assert check_bounds("etf_flows", 100.0) is True
    assert check_bounds("unknown_source", 999.0) is True
    assert check_bounds("fear_greed", None) is True


def test_check_bounds_out_of_range() -> None:
    """check_bounds returns False for values outside defined bounds."""
    assert check_bounds("fear_greed", -1.0) is False
    assert check_bounds("fear_greed", 101.0) is False
    assert check_bounds("funding", 0.1) is False
    assert check_bounds("funding", -0.1) is False
    assert check_bounds("dxy", 25.0) is False
    assert check_bounds("dxy", -25.0) is False
    assert check_bounds("price_ma", 50.0) is False
    assert check_bounds("price_ma", -40.0) is False
    assert check_bounds("etf_flows", 10000.0) is False
    assert check_bounds("etf_flows", -10000.0) is False


def test_out_of_range_result() -> None:
    """out_of_range_result returns FetcherResult with error='out_of_range'."""
    r = out_of_range_result("fear_greed")
    assert r.source_id == "fear_greed"
    assert r.raw_value is None
    assert r.normalized_score is None
    assert r.stale is False
    assert r.error == "out_of_range"


@pytest.mark.asyncio
async def test_fear_greed_out_of_range_returns_error() -> None:
    """Fear & Greed fetcher returns out_of_range when API returns value > 100."""
    import respx
    from httpx import Response

    with respx.mock:
        respx.get("https://api.alternative.me/fng/?limit=1").mock(
            return_value=Response(
                200,
                json={"data": [{"value": "150", "timestamp": "1706630400"}]},
            )
        )
        from app.fetchers.fear_greed import FearGreedFetcher

        result = await FearGreedFetcher().fetch()
    assert result.error == "out_of_range"
    assert result.raw_value is None


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_n_failures() -> None:
    """After N consecutive failures, circuit opens and skips calls."""
    reset_circuits()
    mock_settings = MagicMock()
    mock_settings.circuit_failure_threshold = 1  # open after 1 failure
    mock_settings.circuit_open_seconds = 10.0
    mock_settings.retry_attempts = 1
    mock_settings.retry_base_delay = 0.01

    async def failing_fn() -> FetcherResult:
        raise RuntimeError("simulated failure")

    source_id = "circuit_test_src"
    with patch("app.fetchers.base.get_settings", return_value=mock_settings):
        # First call: fails, circuit opens (threshold=1)
        r1 = await with_retry(source_id, failing_fn)
        assert r1.error is not None
        assert "simulated failure" in (r1.error or "")
        # Second call: circuit open, skip call
        r2 = await with_retry(source_id, failing_fn)
        assert r2.error == "circuit_open"
        assert r2.raw_value is None

    reset_circuits()


@pytest.mark.asyncio
async def test_registry_with_mocks_returns_snapshot_shape() -> None:
    """Run registry with respx mocks; snapshot shape correct, no real API calls."""
    import respx
    from httpx import Response

    # Mock HTTP sources so we don't hit real APIs
    with respx.mock:
        respx.get("https://api.sosovalue.com/api/etf-flows").mock(
            return_value=Response(200, json={"net_flow": 150})
        )
        respx.get("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT").mock(
            return_value=Response(200, json={"lastFundingRate": "0.0001"})
        )
        respx.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?range=5d&interval=1d"
        ).mock(
            return_value=Response(
                200,
                json={
                    "chart": {
                        "result": [
                            {"indicators": {"quote": [{"close": [100.0, 99.0, 98.0, 97.0, 96.0]}]}}
                        ]
                    }
                },
            )
        )
        respx.get("https://api.alternative.me/fng/?limit=1").mock(
            return_value=Response(
                200,
                json={"data": [{"value": "45", "timestamp": "1706630400"}]},
            )
        )
        respx.get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=51").mock(
            return_value=Response(
                200,
                json=[[0, 0, 0, 0, 42000.0 + i] for i in range(51)],
            )
        )

        snapshot = await run_all_fetchers()

    assert isinstance(snapshot, FeatureSnapshot)
    assert len(snapshot.results) == len(get_all_fetchers())
    assert snapshot.timestamp != ""
    for r in snapshot.results:
        assert isinstance(r, FetcherResult)
        assert r.source_id
    # At least some sources should have data (mocked); exchange_netflow and macro are placeholders
    source_ids = {r.source_id for r in snapshot.results}
    assert "etf_flows" in source_ids
    assert "funding" in source_ids
    assert "dxy" in source_ids
    assert "fear_greed" in source_ids
    assert "price_ma" in source_ids
    assert "exchange_netflow" in source_ids
    assert "macro" in source_ids
    # Partial data: some with values, some with error (e.g. circuit or no_api_key)
    with_data = [r for r in snapshot.results if r.raw_value is not None]
    assert len(with_data) >= 4
