"""Exchange netflow: CryptoQuant / Glassnode 7d netflow (BTC). Placeholder if no key."""

from app.fetchers.base import FetcherResult, BaseFetcher
from app.logging_config import get_logger

logger = get_logger(__name__)


class ExchangeNetflowFetcher(BaseFetcher):
    source_id = "exchange_netflow"
    max_age_seconds = 86400

    def normalize(self, raw: str | float | None) -> float | None:
        """Outflow >5k: +2, outflow: +1, inflow: -1, >5k inflow: -2."""
        if raw is None:
            return None
        try:
            v = float(raw)
            if v >= 5000:
                return -2.0
            if v > 0:
                return -1.0
            if v >= -5000:
                return 1.0
            return 2.0
        except (TypeError, ValueError):
            return None

    async def fetch(self) -> FetcherResult:
        # Placeholder: no public free API; return unavailable
        return FetcherResult(
            source_id=self.source_id,
            raw_value=None,
            normalized_score=None,
            stale=False,
            error="no_api_key",
        )
