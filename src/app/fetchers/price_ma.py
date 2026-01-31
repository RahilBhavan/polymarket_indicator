"""Price vs 50 MA: Binance primary; CoinGecko fallback when Binance returns 451 (region block)."""

import time
import httpx
from app.fetchers.base import BaseFetcher, FetcherResult, get_fetcher_timeout, with_retry
from app.fetchers.bounds import check_bounds, out_of_range_result

BINANCE_KLINES = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=51"
COINGECKO_MARKET_CHART = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=60"
# If Binance and CoinGecko last-close diff exceeds this fraction, mark result stale
PRICE_DISCREPANCY_THRESHOLD = 0.01


def _compute_pct_from_closes(closes: list[float]) -> tuple[float, float] | None:
    """Return (pct_deviation, price) or None if insufficient data."""
    if len(closes) < 51:
        return None
    price = closes[-1]
    ma50 = sum(closes[-51:-1]) / 50
    if not ma50:
        return None
    pct = (price - ma50) / ma50 * 100
    return (pct, price)


class PriceMaFetcher(BaseFetcher):
    source_id = "price_ma"
    max_age_seconds = 3600

    def normalize(self, raw: str | float | None) -> float | None:
        """% deviation: >5% above: +1, above: +0.5, below: -0.5, >5% below: -1."""
        if raw is None:
            return None
        try:
            v = float(raw)
            if v >= 5:
                return 1.0
            if v > 0:
                return 0.5
            if v >= -5:
                return -0.5
            return -1.0
        except (TypeError, ValueError):
            return None

    async def _fetch_binance(
        self, client: httpx.AsyncClient
    ) -> tuple[FetcherResult | None, float | None]:
        """Try Binance; return (FetcherResult, last_close_price) or (None, None) on 451/error."""
        try:
            resp = await client.get(BINANCE_KLINES)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 451:
                return (None, None)  # region block; try fallback
            return (self._error_result(e), None)
        except Exception as e:
            return (self._error_result(e), None)
        if len(data) < 51:
            return (
                FetcherResult(
                    source_id=self.source_id,
                    raw_value=None,
                    normalized_score=None,
                    stale=False,
                    error="insufficient_klines",
                ),
                None,
            )
        closes = [float(c[4]) for c in data]
        out = _compute_pct_from_closes(closes)
        if out is None:
            return (
                FetcherResult(
                    source_id=self.source_id,
                    raw_value=None,
                    normalized_score=None,
                    stale=False,
                    error="insufficient_klines",
                ),
                None,
            )
        pct, last_close = out
        if not check_bounds(self.source_id, pct):
            return (out_of_range_result(self.source_id), None)
        score = self.normalize(pct)
        stale = False
        try:
            open_time_ms = int(data[-1][0])
            age_seconds = time.time() - (open_time_ms / 1000.0)
            stale = age_seconds > self.max_age_seconds
        except (TypeError, ValueError, IndexError):
            pass
        return (
            FetcherResult(
                source_id=self.source_id,
                raw_value=f"{pct:.2f}",
                normalized_score=score,
                stale=stale,
            ),
            last_close,
        )

    async def _fetch_coingecko(self, client: httpx.AsyncClient) -> FetcherResult | None:
        """CoinGecko fallback: market_chart 60d, aggregate to ~daily then 50 MA."""
        try:
            resp = await client.get(COINGECKO_MARKET_CHART)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return self._error_result(e)
        prices = data.get("prices") or []
        if len(prices) < 51:
            return FetcherResult(
                source_id=self.source_id,
                raw_value=None,
                normalized_score=None,
                stale=False,
                error="insufficient_klines",
            )
        # prices are [timestamp_ms, price]; take last 51 closes
        closes = [float(p[1]) for p in prices[-51:]]
        out = _compute_pct_from_closes(closes)
        if out is None:
            return FetcherResult(
                source_id=self.source_id,
                raw_value=None,
                normalized_score=None,
                stale=False,
                error="insufficient_klines",
            )
        pct, _ = out
        if not check_bounds(self.source_id, pct):
            return out_of_range_result(self.source_id)
        score = self.normalize(pct)
        stale = False
        try:
            ts_ms = int(prices[-1][0])
            age_seconds = time.time() - (ts_ms / 1000.0)
            stale = age_seconds > self.max_age_seconds
        except (TypeError, ValueError, IndexError):
            pass
        return FetcherResult(
            source_id=self.source_id,
            raw_value=f"{pct:.2f}",
            normalized_score=score,
            stale=stale,
        )

    async def _get_coingecko_last_price(self, client: httpx.AsyncClient) -> float | None:
        """Fetch CoinGecko market_chart and return last close price, or None on error."""
        try:
            resp = await client.get(COINGECKO_MARKET_CHART)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return None
        prices = data.get("prices") or []
        if len(prices) < 1:
            return None
        try:
            return float(prices[-1][1])
        except (TypeError, ValueError, IndexError):
            return None

    async def _do_fetch(self) -> FetcherResult:
        timeout = get_fetcher_timeout()
        async with httpx.AsyncClient(timeout=timeout) as client:
            result, binance_price = await self._fetch_binance(client)
            if result is not None and result.error is None:
                if binance_price is not None and binance_price > 0:
                    cg_price = await self._get_coingecko_last_price(client)
                    if cg_price is not None:
                        diff = abs(binance_price - cg_price) / binance_price
                        if diff > PRICE_DISCREPANCY_THRESHOLD:
                            result = FetcherResult(
                                source_id=result.source_id,
                                raw_value=result.raw_value,
                                normalized_score=result.normalized_score,
                                stale=True,
                                error=result.error,
                            )
                return result
            result_cg = await self._fetch_coingecko(client)
            if result_cg is not None:
                return result_cg
        return self._error_result(RuntimeError("Binance (451) and CoinGecko fallback failed"))

    async def fetch(self) -> FetcherResult:
        return await with_retry(self.source_id, self._do_fetch)
