"""Fear & Greed index: alternative.me 0-100."""

import time

import httpx
from app.fetchers.base import BaseFetcher, FetcherResult, get_fetcher_timeout, with_retry
from app.fetchers.bounds import check_bounds, out_of_range_result

FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"


class FearGreedFetcher(BaseFetcher):
    source_id = "fear_greed"
    max_age_seconds = 86400

    def normalize(self, raw: str | float | None) -> float | None:
        """<25: +2, <40: +1, >60: -1, >80: -2."""
        if raw is None:
            return None
        try:
            v = float(raw)
            if v < 25:
                return 2.0
            if v < 40:
                return 1.0
            if v > 80:
                return -2.0
            if v > 60:
                return -1.0
            return 0.0
        except (TypeError, ValueError):
            return None

    async def _do_fetch(self) -> FetcherResult:
        try:
            async with httpx.AsyncClient(timeout=get_fetcher_timeout()) as client:
                resp = await client.get(FEAR_GREED_URL)
                resp.raise_for_status()
                data = resp.json()
            items = data.get("data", [])
            if not items:
                return FetcherResult(
                    source_id=self.source_id,
                    raw_value=None,
                    normalized_score=None,
                    stale=False,
                    error="no_data",
                )
            item = items[0]
            value = int(item.get("value", 0))
            if not check_bounds(self.source_id, float(value)):
                return out_of_range_result(self.source_id)
            score = self.normalize(value)
            # alternative.me returns "timestamp" (Unix); mark stale if older than max_age
            data_ts = item.get("timestamp")
            stale = False
            if data_ts is not None:
                try:
                    age_seconds = time.time() - int(data_ts)
                    stale = age_seconds > self.max_age_seconds
                except (TypeError, ValueError):
                    pass
            return FetcherResult(
                source_id=self.source_id,
                raw_value=str(value),
                normalized_score=score,
                stale=stale,
            )
        except Exception as e:
            return self._error_result(e)

    async def fetch(self) -> FetcherResult:
        return await with_retry(self.source_id, self._do_fetch)
