"""ETF flows: Farside / SoSoValue daily net flow (USD). URL configurable via ETF_FLOWS_URL."""

import os
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from app.fetchers.base import BaseFetcher, FetcherResult, get_fetcher_timeout, with_retry
from app.fetchers.bounds import check_bounds, out_of_range_result

# Default; override with ETF_FLOWS_URL in .env if domain differs or service moved
DEFAULT_ETF_FLOWS_URL = "https://api.sosovalue.com/api/etf-flows"


class EtfFlowsFetcher(BaseFetcher):
    source_id = "etf_flows"
    max_age_seconds = 86400  # daily

    def normalize(self, raw: str | float | None) -> float | None:
        """Map daily net flow ($M) to score -2..+2. >200: +2, >0: +1, <0: -1, <-200: -2."""
        if raw is None:
            return None
        try:
            v = float(raw)
            if v >= 200:
                return 2.0
            if v >= 0:
                return 1.0
            if v >= -200:
                return -1.0
            return -2.0
        except (TypeError, ValueError):
            return None

    async def _do_fetch(self) -> FetcherResult:
        url = os.getenv("ETF_FLOWS_URL", DEFAULT_ETF_FLOWS_URL).strip() or DEFAULT_ETF_FLOWS_URL
        parsed = urlparse(url)
        if not parsed.netloc or parsed.scheme not in ("http", "https"):
            return FetcherResult(
                source_id=self.source_id,
                raw_value=None,
                normalized_score=None,
                stale=False,
                error="invalid_etf_flows_url",
            )
        try:
            async with httpx.AsyncClient(timeout=get_fetcher_timeout()) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            raw = data.get("btc_etf_net_flow_usd") or data.get("net_flow") or 0
            raw_f = float(raw)
            if not check_bounds(self.source_id, raw_f):
                return out_of_range_result(self.source_id)
            score = self.normalize(raw_f)
            stale = False
            data_ts = (
                data.get("date")
                or data.get("updated")
                or data.get("timestamp")
                or data.get("as_of")
            )
            if data_ts is not None:
                try:
                    if isinstance(data_ts, (int, float)):
                        ts_sec = float(data_ts) / 1000.0 if data_ts > 1e10 else float(data_ts)
                    else:
                        dt = datetime.fromisoformat(str(data_ts).replace("Z", "+00:00"))
                        ts_sec = (
                            dt.timestamp()
                            if dt.tzinfo
                            else dt.replace(tzinfo=timezone.utc).timestamp()
                        )
                    age_seconds = time.time() - ts_sec
                    stale = age_seconds > self.max_age_seconds
                except (TypeError, ValueError):
                    pass
            return FetcherResult(
                source_id=self.source_id,
                raw_value=str(raw_f),
                normalized_score=score,
                stale=stale,
            )
        except Exception as e:
            return self._error_result(e)

    async def fetch(self) -> FetcherResult:
        return await with_retry(self.source_id, self._do_fetch)
