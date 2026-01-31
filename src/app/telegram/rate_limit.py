"""Rate limit Telegram sends: max 1 message per min_interval_seconds per chat (stay under 30 msg/s)."""

import asyncio
import time

# Minimum seconds between sends per chat (0.5s => max 2/s per chat; 30/s global with many users)
MIN_INTERVAL_SECONDS = 0.5

_locks: dict[int, asyncio.Lock] = {}
_last_send: dict[int, float] = {}


def _get_lock(chat_id: int) -> asyncio.Lock:
    if chat_id not in _locks:
        _locks[chat_id] = asyncio.Lock()
    return _locks[chat_id]


async def wait_if_needed(chat_id: int) -> None:
    """
    Wait so that we don't send more than 1 message per MIN_INTERVAL_SECONDS for this chat.
    Call before sending a message.
    """
    lock = _get_lock(chat_id)
    async with lock:
        now = time.monotonic()
        last = _last_send.get(chat_id, 0.0)
        elapsed = now - last
        if elapsed < MIN_INTERVAL_SECONDS:
            await asyncio.sleep(MIN_INTERVAL_SECONDS - elapsed)
        _last_send[chat_id] = time.monotonic()
