"""Rate limiter: wait_if_needed throttles per chat."""

import asyncio
import time

import pytest

from app.telegram.rate_limit import MIN_INTERVAL_SECONDS, wait_if_needed


@pytest.mark.asyncio
async def test_wait_if_needed_throttles_per_chat() -> None:
    """First call returns quickly; second call within min interval waits."""
    chat_id = 99999
    t0 = time.monotonic()
    await wait_if_needed(chat_id)
    await wait_if_needed(chat_id)
    elapsed2 = time.monotonic() - t0
    # Second call should have waited at least (MIN_INTERVAL - epsilon)
    assert elapsed2 >= MIN_INTERVAL_SECONDS * 0.9


@pytest.mark.asyncio
async def test_wait_if_needed_different_chats_independent() -> None:
    """Different chat_ids do not block each other."""
    t0 = time.monotonic()
    await asyncio.gather(wait_if_needed(100), wait_if_needed(101), wait_if_needed(102))
    elapsed = time.monotonic() - t0
    # All three can proceed without waiting for each other (same lock per chat)
    assert elapsed < MIN_INTERVAL_SECONDS * 2
