"""Telegram API helpers: send message, answer callback."""

from typing import Any

import httpx

from app.logging_config import get_logger
from app.telegram.rate_limit import wait_if_needed

BASE_URL = "https://api.telegram.org/bot"
logger = get_logger(__name__)


async def send_message(
    token: str,
    chat_id: int,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: dict[str, Any] | None = None,
) -> None:
    """Send a text message to a chat. Rate-limited per chat. Raises on Telegram API or connection failure."""
    await wait_if_needed(chat_id)
    url = f"{BASE_URL}{token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.warning("send_message_failed", chat_id=chat_id, error=str(e))
        raise


async def answer_callback(token: str, callback_query_id: str, text: str | None = None) -> None:
    """Answer an inline callback query."""
    url = f"{BASE_URL}{token}/answerCallbackQuery"
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text[:200]
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(url, json=payload)
