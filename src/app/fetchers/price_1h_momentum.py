"""1h price momentum: last closed 1h candle return from Binance for hourly Up/Down signals."""

import httpx

from app.fetchers.base import BaseFetcher, FetcherResult, get_fetcher_timeout, with_retry

BINANCE_KLINES_1H = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=4"


def _last_closed_1h_return(klines: list) -> float | None:
    """
    Compute r_1h = (C_{t-1} - O_{t-1}) / O_{t-1} for the last closed 1h candle.
    klines: list of [open_time, open, high, low, close, ...]; index 1=open, 4=close.
    """
    if len(klines) < 2:
        return None
    # Last closed = second-to-last candle (last may still be open)
    candle = klines[-2]
    try:
        o = float(candle[1])
        c = float(candle[4])
    except (IndexError, TypeError, ValueError):
        return None
    if o <= 0:
        return None
    return (c - o) / o


class Price1hMomentumFetcher(BaseFetcher):
    """Fetches last 2–4 1h klines from Binance and normalizes last closed 1h return to -2..+2."""

    source_id = "price_1h_momentum"
    max_age_seconds = 600  # 10 min

    def normalize(self, raw: float | None) -> float | None:
        """
        Map 1h return to score in [-2, 2].
        Simple thresholds: large positive -> +2, large negative -> -2.
        """
        if raw is None:
            return None
        try:
            r = float(raw)
            # e.g. >1% -> +1, >0.5% -> +0.5, <-0.5% -> -0.5, <-1% -> -1; scale to ±2
            pct = r * 100
            if pct >= 1.0:
                return 2.0
            if pct >= 0.5:
                return 1.0
            if pct >= 0.1:
                return 0.5
            if pct >= -0.1:
                return 0.0
            if pct >= -0.5:
                return -0.5
            if pct >= -1.0:
                return -1.0
            return -2.0
        except (TypeError, ValueError):
            return None

    async def _do_fetch(self) -> FetcherResult:
        timeout = get_fetcher_timeout()
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.get(BINANCE_KLINES_1H)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                return self._error_result(e)
        if not data or len(data) < 2:
            return FetcherResult(
                source_id=self.source_id,
                raw_value=None,
                normalized_score=None,
                stale=False,
                error="insufficient_klines",
            )
        r_1h = _last_closed_1h_return(data)
        if r_1h is None:
            return FetcherResult(
                source_id=self.source_id,
                raw_value=None,
                normalized_score=None,
                stale=False,
                error="insufficient_klines",
            )
        score = self.normalize(r_1h)
        pct_str = f"{r_1h * 100:.2f}%"
        return FetcherResult(
            source_id=self.source_id,
            raw_value=pct_str,
            normalized_score=score,
            stale=False,
        )

    async def fetch(self) -> FetcherResult:
        return await with_retry(self.source_id, self._do_fetch)
