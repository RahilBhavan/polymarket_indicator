"""Coinbase premium: US vs global spread (CryptoQuant / TradingView). Optional fetcher; placeholder until API wired."""

from app.fetchers.base import FetcherResult, BaseFetcher


class CoinbasePremiumFetcher(BaseFetcher):
    """US vs global BTC spread; positive premium can be bullish. Placeholder returns neutral score."""

    source_id = "coinbase_premium"
    max_age_seconds = 3600

    def normalize(self, raw: str | float | None) -> float | None:
        """Map premium (e.g. bps) to -2..+2. Placeholder returns None."""
        if raw is None:
            return None
        try:
            v = float(raw)
            # Example: >50 bps -> +1, <-50 -> -1
            if v > 0.005:
                return min(2.0, v * 100)
            if v < -0.005:
                return max(-2.0, v * 100)
            return 0.0
        except (TypeError, ValueError):
            return None

    async def fetch(self) -> FetcherResult:
        # Placeholder: no API; return neutral so composite is unchanged until wired
        return FetcherResult(
            source_id=self.source_id,
            raw_value="placeholder",
            normalized_score=0.0,
            stale=False,
        )
