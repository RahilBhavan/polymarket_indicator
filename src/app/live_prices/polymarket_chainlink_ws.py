"""Polymarket live WebSocket: crypto_prices_chainlink topic (BTC)."""

import asyncio
import json
from dataclasses import dataclass

import websockets
from websockets.legacy.client import WebSocketClientProtocol

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PolymarketWsTick:
    """Last price from Polymarket WS."""

    price: float | None = None
    updated_at_ms: int | None = None
    source: str = "polymarket_ws"


_last: PolymarketWsTick = PolymarketWsTick()
_ws: WebSocketClientProtocol | None = None
_task: asyncio.Task | None = None
_reconnect_delay = 0.5
_symbol_filter = "btc"


def _parse_price_message(msg: str) -> tuple[float | None, int | None]:
    """Parse WS message; return (price, updated_at_ms) or (None, None)."""
    try:
        data = json.loads(msg)
    except (json.JSONDecodeError, TypeError):
        return (None, None)
    if data.get("topic") != "crypto_prices_chainlink":
        return (None, None)
    payload = data.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return (None, None)
    if not isinstance(payload, dict):
        return (None, None)
    symbol = str(payload.get("symbol") or payload.get("pair") or payload.get("ticker") or "").lower()
    if _symbol_filter not in symbol:
        return (None, None)
    raw_price = payload.get("value") or payload.get("price") or payload.get("current") or payload.get("data")
    try:
        price = float(raw_price)
    except (TypeError, ValueError):
        return (None, None)
    ts = payload.get("timestamp") or payload.get("updatedAt")
    if ts is not None:
        try:
            updated_at_ms = int(float(ts) * 1000)
        except (TypeError, ValueError):
            updated_at_ms = None
    else:
        updated_at_ms = None
    return (price, updated_at_ms)


def get_last() -> PolymarketWsTick:
    """Return last tick from Polymarket WS (may be empty if not connected)."""
    return _last


async def _run_loop() -> None:
    """Connect, subscribe, and process messages with reconnect backoff."""
    global _last, _ws, _reconnect_delay, _task
    settings = get_settings()
    url = settings.polymarket_live_ws_url
    if not url:
        return
    while True:
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
                await sock.send(
                    json.dumps(
                        {
                            "action": "subscribe",
                            "subscriptions": [
                                {"topic": "crypto_prices_chainlink", "type": "*", "filters": ""}
                            ],
                        }
                    )
                )
                async for raw in sock:
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8", errors="replace")
                    price, updated_at_ms = _parse_price_message(raw)
                    if price is not None:
                        _last = PolymarketWsTick(
                            price=price,
                            updated_at_ms=updated_at_ms,
                            source="polymarket_ws",
                        )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("polymarket_ws_error", error=str(e))
        _ws = None
        await asyncio.sleep(_reconnect_delay)
        _reconnect_delay = min(10.0, _reconnect_delay * 1.5)


def start_background() -> None:
    """Start the Polymarket WS background task (idempotent)."""
    global _task
    if _task is not None and not _task.done():
        return
    loop = asyncio.get_event_loop()
    _task = loop.create_task(_run_loop())
    logger.info("polymarket_ws_started")


def stop_background() -> None:
    """Cancel the background task."""
    global _task
    if _task is not None:
        _task.cancel()
        _task = None
    global _ws
    _ws = None
