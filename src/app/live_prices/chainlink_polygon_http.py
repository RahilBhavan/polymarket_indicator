"""Chainlink BTC/USD on Polygon via HTTP JSON-RPC (latestRoundData)."""

import time
from dataclasses import dataclass

import httpx
from eth_abi import decode

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# latestRoundData() selector: first 4 bytes of keccak256("latestRoundData()")
LATEST_ROUND_DATA_SELECTOR = "0xfeaf968c"
DECIMALS_SELECTOR = "0x313ce567"  # decimals()
RPC_TIMEOUT = 1.5
MIN_FETCH_INTERVAL = 2.0  # seconds; overridden by config


@dataclass
class ChainlinkResult:
    """Result of a Chainlink price fetch."""

    price: float | None
    updated_at_ms: int | None
    source: str = "chainlink_http"


_cached: ChainlinkResult | None = None
_cached_at: float = 0.0


def _rpc_urls() -> list[str]:
    """Ordered list of Polygon RPC URLs to try."""
    settings = get_settings()
    from_list = [s.strip() for s in settings.polygon_rpc_urls.split(",") if s.strip()]
    single = [settings.polygon_rpc_url] if settings.polygon_rpc_url else []
    return from_list if from_list else single


async def _eth_call(rpc_url: str, to: str, data: str) -> str | None:
    """Execute eth_call; return result hex or None."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"],
    }
    try:
        async with httpx.AsyncClient(timeout=RPC_TIMEOUT) as client:
            resp = await client.post(
                rpc_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            out = resp.json()
    except Exception as e:
        logger.warning("chainlink_http_eth_call_failed", url=rpc_url, error=str(e))
        return None
    err = out.get("error")
    if err:
        logger.warning("chainlink_http_rpc_error", code=err.get("code"), message=err.get("message"))
        return None
    return out.get("result")


def _decode_latest_round_data(result_hex: str) -> tuple[int, int] | None:
    """Decode latestRoundData return: (answer: int, updated_at: int)."""
    if not result_hex or not result_hex.startswith("0x"):
        return None
    raw = bytes.fromhex(result_hex[2:])
    if len(raw) < 32 * 5:
        return None
    # (uint80 roundId, int256 answer, uint256 startedAt, uint256 updatedAt, uint80 answeredInRound)
    try:
        decoded = decode(
            ["uint80", "int256", "uint256", "uint256", "uint80"],
            raw,
        )
        answer = decoded[1]
        updated_at = decoded[3]
        return (answer, updated_at)
    except Exception as e:
        logger.warning("chainlink_decode_failed", error=str(e))
        return None


async def fetch_chainlink_btc_usd() -> ChainlinkResult:
    """
    Fetch BTC/USD price from Chainlink aggregator on Polygon via HTTP.
    Uses multiple RPC URLs on failure. Caches result for a short interval.
    """
    global _cached, _cached_at
    settings = get_settings()
    aggregator = settings.chainlink_btc_usd_aggregator
    if not aggregator:
        return ChainlinkResult(price=None, updated_at_ms=None, source="missing_config")

    now = time.monotonic()
    if _cached is not None and (now - _cached_at) < settings.chainlink_http_cache_seconds:
        return _cached

    urls = _rpc_urls()
    if not urls:
        return ChainlinkResult(price=None, updated_at_ms=None, source="missing_config")

    decimals_cache: int | None = None
    for rpc_url in urls:
        # Fetch decimals once
        if decimals_cache is None:
            dec_result = await _eth_call(rpc_url, aggregator, DECIMALS_SELECTOR)
            if dec_result:
                try:
                    dec_raw = bytes.fromhex(dec_result[2:].ljust(64, "0")[:64])
                    (decimals_cache,) = decode(["uint8"], dec_raw)
                except (ValueError, TypeError, Exception):
                    pass
        round_result = await _eth_call(rpc_url, aggregator, LATEST_ROUND_DATA_SELECTOR)
        if not round_result:
            continue
        decoded = _decode_latest_round_data(round_result)
        if not decoded:
            continue
        answer, updated_at = decoded
        scale = 10 ** (decimals_cache or 8)
        price = answer / scale
        updated_at_ms = int(updated_at) * 1000
        result = ChainlinkResult(price=price, updated_at_ms=updated_at_ms, source="chainlink_http")
        _cached = result
        _cached_at = now
        return result

    return _cached or ChainlinkResult(price=None, updated_at_ms=None, source="chainlink_http")
