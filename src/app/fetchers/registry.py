"""Run all fetchers in parallel and aggregate into feature snapshot."""

import asyncio
import datetime
from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings
from app.fetchers.base import FetcherResult
from app.fetchers.coinbase_premium import CoinbasePremiumFetcher
from app.fetchers.dxy import DxyFetcher
from app.fetchers.etf_flows import EtfFlowsFetcher
from app.fetchers.exchange_netflow import ExchangeNetflowFetcher
from app.fetchers.fear_greed import FearGreedFetcher
from app.fetchers.funding import FundingFetcher
from app.fetchers.macro import MacroFetcher
from app.fetchers.price_1h_momentum import Price1hMomentumFetcher
from app.fetchers.price_ma import PriceMaFetcher
from app.fetchers.stablecoin_issuance import StablecoinIssuanceFetcher
from app.logging_config import get_logger
from app.polymarket.models import Market
from app.polymarket.selection import is_btc_up_down_hourly_market
from app.signal.weights import HOURLY_WEIGHTS, get_weights

logger = get_logger(__name__)


@dataclass
class FeatureSnapshot:
    """Aggregated snapshot: list of FetcherResult, timestamp."""

    results: list[FetcherResult] = field(default_factory=list)
    timestamp: str = ""

    def to_rows(self) -> list[dict[str, Any]]:
        """For DB insert: list of {source_id, raw_value, normalized_score, stale}."""
        return [
            {
                "source_id": r.source_id,
                "raw_value": r.raw_value,
                "normalized_score": r.normalized_score,
                "stale": r.stale,
            }
            for r in self.results
        ]


def get_all_fetchers() -> list[Any]:
    """Return list of fetcher instances. Optional fetchers included when env flags are set."""
    settings = get_settings()
    fetchers: list[Any] = [
        EtfFlowsFetcher(),
        FundingFetcher(),
        DxyFetcher(),
        FearGreedFetcher(),
        PriceMaFetcher(),
        ExchangeNetflowFetcher(),
        MacroFetcher(),
    ]
    if settings.fetch_coinbase_premium:
        fetchers.append(CoinbasePremiumFetcher())
    if settings.fetch_stablecoin_issuance:
        fetchers.append(StablecoinIssuanceFetcher())
    return fetchers


async def _run_fetchers_async(fetchers: list[Any]) -> list[FetcherResult]:
    """Run given fetchers in parallel; return list of FetcherResult."""
    results = await asyncio.gather(*[f.fetch() for f in fetchers], return_exceptions=True)
    out: list[FetcherResult] = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            fid = fetchers[i].source_id if i < len(fetchers) else "unknown"
            out.append(
                FetcherResult(
                    source_id=fid,
                    raw_value=None,
                    normalized_score=None,
                    stale=False,
                    error=str(r),
                )
            )
        elif isinstance(r, FetcherResult):
            out.append(r)
    return out


async def run_fetchers_for_market(market: Market) -> tuple[FeatureSnapshot, dict[str, float]]:
    """
    Run fetchers appropriate for the market; return (snapshot, weights).
    For hourly Up/Down: run all fetchers + Price1hMomentumFetcher and return HOURLY_WEIGHTS.
    Else: run_all_fetchers() and get_weights().
    """
    if is_btc_up_down_hourly_market(market):
        fetchers = get_all_fetchers() + [Price1hMomentumFetcher()]
        results = await _run_fetchers_async(fetchers)
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        logger.info(
            "fetchers_complete",
            count=len(results),
            errors=sum(1 for x in results if x.error),
            market_type="hourly",
        )
        return FeatureSnapshot(results=results, timestamp=ts), dict(HOURLY_WEIGHTS)
    snapshot = await run_all_fetchers()
    return snapshot, get_weights()


async def run_all_fetchers() -> FeatureSnapshot:
    """Run all fetchers in parallel; return FeatureSnapshot."""
    fetchers = get_all_fetchers()
    results = await _run_fetchers_async(fetchers)
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    logger.info("fetchers_complete", count=len(results), errors=sum(1 for x in results if x.error))
    return FeatureSnapshot(results=results, timestamp=ts)
