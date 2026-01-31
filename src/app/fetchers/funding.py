"""Funding rate: Binance Futures primary; Bybit fallback when Binance returns 451 (region block)."""

import time
import httpx
from app.fetchers.base import BaseFetcher, FetcherResult, get_fetcher_timeout, with_retry
from app.fetchers.bounds import check_bounds, out_of_range_result

BINANCE_FUNDING = "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT"
BYBIT_FUNDING = "https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=1"


class FundingFetcher(BaseFetcher):
    source_id = "funding"
    max_age_seconds = 28800  # 8h

    def normalize(self, raw: str | float | None) -> float | None:
        """Negative funding: +1 (bullish), neutral: 0, high positive: -1 (bearish)."""
        if raw is None:
            return None
        try:
            v = float(raw) * 100  # to %
            if v < -0.01:
                return 1.0
            if v <= 0.03:
                return 0.0
            return -1.0
        except (TypeError, ValueError):
            return None

    def _result(self, last_funding: float, stale: bool = False) -> FetcherResult:
        score = self.normalize(last_funding)
        return FetcherResult(
            source_id=self.source_id,
            raw_value=str(last_funding),
            normalized_score=score,
            stale=stale,
        )

    async def _fetch_binance(self, client: httpx.AsyncClient) -> FetcherResult | None:
        """Try Binance; return FetcherResult or None on 451/error."""
        try:
            resp = await client.get(BINANCE_FUNDING)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 451:
                return None
            return self._error_result(e)
        except Exception as e:
            return self._error_result(e)
        last_funding = float(data.get("lastFundingRate", 0))
        if not check_bounds(self.source_id, last_funding):
            return out_of_range_result(self.source_id)
        stale = False
        server_time_ms = data.get("time")
        if server_time_ms is not None:
            try:
                age_seconds = time.time() - (int(server_time_ms) / 1000.0)
                stale = age_seconds > self.max_age_seconds
            except (TypeError, ValueError):
                pass
        return self._result(last_funding, stale=stale)

    async def _fetch_bybit(self, client: httpx.AsyncClient) -> FetcherResult | None:
        """Bybit fallback: latest funding rate."""
        try:
            resp = await client.get(BYBIT_FUNDING)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return self._error_result(e)
        result = data.get("result", {})
        list_ = result.get("list") or []
        if not list_:
            return FetcherResult(
                source_id=self.source_id,
                raw_value=None,
                normalized_score=None,
                stale=False,
                error="no_funding_data",
            )
        # list: [ { "fundingRate": "0.0001", "fundingRateTimestamp": ms }, ... ]; newest first
        item = list_[0]
        last_funding = float(item.get("fundingRate", 0))
        if not check_bounds(self.source_id, last_funding):
            return out_of_range_result(self.source_id)
        stale = False
        ts_ms = item.get("fundingRateTimestamp")
        if ts_ms is not None:
            try:
                age_seconds = time.time() - (int(ts_ms) / 1000.0)
                stale = age_seconds > self.max_age_seconds
            except (TypeError, ValueError):
                pass
        return self._result(last_funding, stale=stale)

    async def _do_fetch(self) -> FetcherResult:
        timeout = get_fetcher_timeout()
        async with httpx.AsyncClient(timeout=timeout) as client:
            result = await self._fetch_binance(client)
            if result is not None:
                return result
            result = await self._fetch_bybit(client)
            if result is not None:
                return result
        return self._error_result(RuntimeError("Binance (451) and Bybit fallback failed"))

    async def fetch(self) -> FetcherResult:
        return await with_retry(self.source_id, self._do_fetch)
