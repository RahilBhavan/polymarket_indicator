"""DXY: 5-day trend % (Yahoo Finance). Retries once on 429 rate limit."""

import asyncio
import time
import httpx
from app.fetchers.base import BaseFetcher, FetcherResult, get_fetcher_timeout, with_retry
from app.fetchers.bounds import check_bounds, out_of_range_result

DXY_URL = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?range=5d&interval=1d"
DXY_429_RETRY_DELAY = 5.0  # seconds before retry on rate limit


class DxyFetcher(BaseFetcher):
    source_id = "dxy"
    max_age_seconds = 86400

    def normalize(self, raw: str | float | None) -> float | None:
        """5d trend %: down >1%: +2, down: +1, up: -1, up >1%: -2."""
        if raw is None:
            return None
        try:
            v = float(raw)
            if v <= -1:
                return 2.0
            if v < 0:
                return 1.0
            if v <= 1:
                return -1.0
            return -2.0
        except (TypeError, ValueError):
            return None

    async def _do_fetch(self) -> FetcherResult:
        timeout = get_fetcher_timeout()
        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(DXY_429_MAX_ATTEMPTS):
                try:
                    resp = await client.get(DXY_URL)
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429 and attempt < DXY_429_MAX_ATTEMPTS - 1:
                        await asyncio.sleep(DXY_429_RETRY_DELAY)
                        continue
                    return self._error_result(e)
                except Exception as e:
                    return self._error_result(e)
            else:
                return self._error_result(RuntimeError("DXY 429 after retry"))
        try:
            chart = data.get("chart", {}).get("result", [{}])[0] if data else {}
            quotes = chart.get("indicators", {}).get("quote", [{}])[0]
            closes = quotes.get("close") or []
            if len(closes) < 2:
                return FetcherResult(
                    source_id=self.source_id,
                    raw_value=None,
                    normalized_score=None,
                    stale=False,
                    error="insufficient_data",
                )
            first = float(closes[0])
            last = float(closes[-1])
            pct = ((last - first) / first * 100) if first else 0
            if not check_bounds(self.source_id, pct):
                return out_of_range_result(self.source_id)
            score = self.normalize(pct)
            stale = False
            timestamps = chart.get("timestamp") or []
            if timestamps:
                try:
                    last_ts = int(timestamps[-1])
                    age_seconds = time.time() - last_ts
                    stale = age_seconds > self.max_age_seconds
                except (TypeError, ValueError, IndexError):
                    pass
            return FetcherResult(
                source_id=self.source_id,
                raw_value=f"{pct:.2f}",
                normalized_score=score,
                stale=stale,
            )
        except Exception as e:
            return self._error_result(e)

    async def fetch(self) -> FetcherResult:
        return await with_retry(self.source_id, self._do_fetch)
