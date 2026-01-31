"""Chainlink BTC/USD on Polygon via WSS eth_subscribe logs (AnswerUpdated)."""

import asyncio
import json
from dataclasses import dataclass

import websockets
from websockets.legacy.client import WebSocketClientProtocol

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# AnswerUpdated(int256 answer, uint256 roundId, uint256 updatedAt) - topic0 is event sig
# keccak256("AnswerUpdated(int256,uint256,uint256)") = 0x...
ANSWER_UPDATED_TOPIC0 = "0x0559884fd3a460db3073b7fc896cc77986f16e3782ede84b58e76676e0d1c3f"


@dataclass
class ChainlinkWsTick:
    """Last price from Chainlink Polygon WSS."""

    price: float | None = None
    updated_at_ms: int | None = None
    source: str = "chainlink_ws"


_last: ChainlinkWsTick = ChainlinkWsTick()
_ws: WebSocketClientProtocol | None = None
_task: asyncio.Task | None = None
_sub_id: str | None = None
_reconnect_delay = 0.5
_decimals = 8


def _wss_urls() -> list[str]:
    """List of Polygon WSS URLs."""
    settings = get_settings()
    from_list = [s.strip() for s in settings.polygon_wss_urls.split(",") if s.strip()]
    single = [settings.polygon_wss_url] if settings.polygon_wss_url else []
    return from_list if from_list else single


def get_last() -> ChainlinkWsTick:
    """Return last tick from Chainlink WSS."""
    return _last


def _decode_log(log: dict) -> tuple[float | None, int | None]:
    """Decode AnswerUpdated log: topics[1]=answer (int256), data=updatedAt (uint256)."""
    global _decimals
    topics = log.get("topics") or []
    if len(topics) < 2:
        return (None, None)
    try:
        answer_hex = topics[1]
        answer = int(answer_hex, 16)
        if answer >= 2**255:
            answer -= 2**256
        price = answer / (10**_decimals)
    except (ValueError, TypeError):
        return (None, None)
    data_hex = log.get("data")
    updated_at_ms = None
    if data_hex:
        try:
            updated_at = int(data_hex, 16)
            updated_at_ms = updated_at * 1000
        except (ValueError, TypeError):
            pass
    return (price, updated_at_ms)


async def _run_loop() -> None:
    """Connect to Polygon WSS, subscribe to logs, process with reconnect."""
    global _last, _ws, _sub_id, _reconnect_delay, _decimals, _task
    settings = get_settings()
    aggregator = settings.chainlink_btc_usd_aggregator
    urls = _wss_urls()
    if not aggregator or not urls:
        return
    url_index = 0
    while True:
        url = urls[url_index % len(urls)]
        url_index += 1
        try:
            async with websockets.connect(
                url,
                open_timeout=10,
                close_timeout=5,
                ping_interval=20,
                ping_timeout=10,
            ) as sock:
                _ws = sock
                _reconnect_delay = 0.5
                req = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_subscribe",
                    "params": [
                        "logs",
                        {"address": aggregator, "topics": [ANSWER_UPDATED_TOPIC0]},
                    ],
                }
                await sock.send(json.dumps(req))
                raw = await sock.recv()
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                msg = json.loads(raw)
                if msg.get("result") and isinstance(msg["result"], str):
                    _sub_id = msg["result"]
                async for raw_msg in sock:
                    if isinstance(raw_msg, bytes):
                        raw_msg = raw_msg.decode("utf-8", errors="replace")
                    try:
                        m = json.loads(raw_msg)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if m.get("method") != "eth_subscription":
                        continue
                    params = m.get("params") or {}
                    result = params.get("result")
                    if not result:
                        continue
                    price, updated_at_ms = _decode_log(result)
                    if price is not None:
                        _last = ChainlinkWsTick(
                            price=price,
                            updated_at_ms=updated_at_ms,
                            source="chainlink_ws",
                        )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("chainlink_ws_error", url=url, error=str(e))
        _ws = None
        _sub_id = None
        await asyncio.sleep(_reconnect_delay)
        _reconnect_delay = min(10.0, _reconnect_delay * 1.5)


def start_background() -> None:
    """Start Chainlink WSS background task (idempotent)."""
    global _task
    if _task is not None and not _task.done():
        return
    if not _wss_urls():
        return
    loop = asyncio.get_event_loop()
    _task = loop.create_task(_run_loop())
    logger.info("chainlink_ws_started")


def stop_background() -> None:
    """Cancel the background task."""
    global _task, _sub_id, _ws
    if _task is not None:
        _task.cancel()
        _task = None
    _sub_id = None
    _ws = None
