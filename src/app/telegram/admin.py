"""Admin alerts: send short message to ADMIN_CHAT_ID on critical errors."""

from typing import Any

import httpx
from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

BASE_URL = "https://api.telegram.org/bot"


async def send_admin_alert(message: str) -> None:
    """Send message to admin chat. No secrets; short error type + timestamp."""
    settings = get_settings()
    if not settings.admin_chat_id:
        logger.warning("admin_alert_skipped", reason="ADMIN_CHAT_ID not set")
        return
    token = settings.telegram_bot_token
    url = f"{BASE_URL}{token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": settings.admin_chat_id,
        "text": message[:4000],
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
    except Exception as e:
        logger.warning("admin_alert_failed", error=str(e))
