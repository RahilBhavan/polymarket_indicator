"""Webhook request verification: X-Telegram-Bot-Api-Secret-Token must match."""

from fastapi import HTTPException, Request

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

HEADER_NAME = "X-Telegram-Bot-Api-Secret-Token"


def verify_telegram_webhook(request: Request) -> None:
    """Verify secret token. Raises 403 if missing or wrong. Do not log token."""
    settings = get_settings()
    secret = request.headers.get(HEADER_NAME)
    if not secret or secret != settings.telegram_webhook_secret:
        logger.warning("webhook_unauthorized", header_present=bool(secret))
        raise HTTPException(status_code=403, detail="Forbidden")
