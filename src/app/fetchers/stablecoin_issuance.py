"""Stablecoin issuance: 24h change in market cap (proxy for supply). CoinGecko free API."""

import httpx
from app.fetchers.base import BaseFetcher, FetcherResult, get_fetcher_timeout, with_retry
from app.fetchers.bounds import check_bounds, out_of_range_result

# CoinGecko markets: USDT + USDC; market_cap_change_percentage_24h ~ supply change for stablecoins
COINGECKO_MARKETS = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&ids=tether,usd-coin&order=market_cap_desc&per_page=2"
)


class StablecoinIssuanceFetcher(BaseFetcher):
    """24h % change in stablecoin market cap (proxy for supply); expansion can be bullish."""

    source_id = "stablecoin_issuance"
    max_age_seconds = 86400

    def normalize(self, raw: str | float | None) -> float | None:
        """Map 24h % change to -2..+2. >1% -> +1, <-1% -> -1, else 0. Raw in % (1 = 1%)."""
        if raw is None:
            return None
        try:
            v = float(raw)
            if v > 1.0:
                return min(2.0, 1.0 + (v - 1.0) * 0.5)
            if v > 0.1:
                return 0.5
            if v < -1.0:
                return max(-2.0, -1.0 + (v + 1.0) * 0.5)
            if v < -0.1:
                return -0.5
            return 0.0
        except (TypeError, ValueError):
            return None

    async def _do_fetch(self) -> FetcherResult:
        try:
            async with httpx.AsyncClient(timeout=get_fetcher_timeout()) as client:
                resp = await client.get(COINGECKO_MARKETS)
                resp.raise_for_status()
                data = resp.json()
            if not isinstance(data, list) or len(data) < 1:
                return FetcherResult(
                    source_id=self.source_id,
                    raw_value=None,
                    normalized_score=None,
                    stale=False,
                    error="no_data",
                )
            # Average 24h market cap change for USDT/USDC (proxy for stablecoin supply change)
            changes: list[float] = []
            for item in data:
                val = item.get("market_cap_change_percentage_24h")
                if val is not None:
                    try:
                        changes.append(float(val))
                    except (TypeError, ValueError):
                        pass
            if not changes:
                return FetcherResult(
                    source_id=self.source_id,
                    raw_value=None,
                    normalized_score=None,
                    stale=False,
                    error="no_24h_change",
                )
            pct = sum(changes) / len(changes)
            if not check_bounds(self.source_id, pct):
                return out_of_range_result(self.source_id)
            score = self.normalize(pct)
            return FetcherResult(
                source_id=self.source_id,
                raw_value=f"{pct:.4f}",
                normalized_score=score,
                stale=False,
            )
        except Exception as e:
            return self._error_result(e)

    async def fetch(self) -> FetcherResult:
        return await with_retry(self.source_id, self._do_fetch)
