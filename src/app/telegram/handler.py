"""Telegram command handler: /start, /status, /help. Whitelist enforced."""

from typing import Any

from app.config import get_settings
from app.db.session import health_check
from app.logging_config import get_logger
from app.telegram.commands import (
    get_settings_keyboard,
    handle_full_details,
    handle_history,
    handle_signal,
    handle_signal_15m,
    handle_signal_hourly5,
    handle_settings_callback,
    handle_stats,
)
from app.telegram.send import answer_callback, send_message

logger = get_logger(__name__)


def _is_allowed(user_id: int) -> bool:
    settings = get_settings()
    return user_id in settings.allowed_user_ids_list()


async def handle_update(update: dict[str, Any]) -> None:
    """
    Process incoming Update. Only process if from whitelisted user.
    Dispatches messages and callback_query.
    """
    settings = get_settings()
    token = settings.telegram_bot_token
    callback = update.get("callback_query")
    if callback:
        await _handle_callback(token, callback, settings.allowed_user_ids_list())
        return
    message = update.get("message") or update.get("edited_message")
    if not message:
        return
    chat_id = message.get("chat", {}).get("id")
    user_id = message.get("from", {}).get("id")
    text = (message.get("text") or "").strip()
    if not user_id or chat_id is None:
        return
    if not _is_allowed(user_id):
        logger.info("command_ignored_unauthorized", user_id=user_id)
        await send_message(token, chat_id, "You are not authorized to use this bot.")
        return
    command = text.split()[0] if text else ""
    if command == "/start":
        await send_message(
            token,
            chat_id,
            "CryptoSignal Bot (Polymarket BTC hourly + daily).\n\n"
            "Commands: /signal, /hourly5, /signal15m, /status, /help\n"
            "/hourly5 = next 5 hourly markets so you can place bets in advance.",
        )
        logger.info("command_handled", command="/start", user_id=user_id)
    elif command == "/status":
        db_ok = False
        try:
            db_ok = await health_check()
        except Exception as e:
            logger.warning("status_health_check_error", error=str(e))
        status = "OK" if db_ok else "DB unavailable"
        await send_message(
            token,
            chat_id,
            f"Status: {status}\nDB: {'connected' if db_ok else 'disconnected'}",
        )
        logger.info("command_handled", command="/status", user_id=user_id, db_ok=db_ok)
    elif command == "/help":
        await send_message(
            token,
            chat_id,
            "Commands:\n"
            "/start - Welcome\n"
            "/status - Bot and DB health\n"
            "/signal - Current/next hourly or daily BTC signal\n"
            "/hourly5 - Next 5 hourly BTC Up/Down (place bets up to 5h ahead)\n"
            "/signal15m - BTC 15m Up/Down signal\n"
            "/stats - Win rate, calibration, streak, drawdown\n"
            "/history [n] - Last n signals with outcome\n"
            "/settings - View config (bankroll, threshold)\n"
            "/help - This message",
        )
        logger.info("command_handled", command="/help", user_id=user_id)
    elif command == "/signal":
        await handle_signal(token, chat_id, user_id)
    elif command in ("/hourly5", "/signal5"):
        await handle_signal_hourly5(token, chat_id, user_id)
    elif command in ("/signal15m", "/signal_15m"):
        await handle_signal_15m(token, chat_id, user_id)
    elif command == "/stats":
        await handle_stats(token, chat_id, user_id)
    elif command.startswith("/history"):
        n = 10
        parts = text.split()
        if len(parts) >= 2:
            try:
                n = min(30, max(1, int(parts[1])))
            except ValueError:
                pass
        await handle_history(token, chat_id, user_id, n)
    elif command == "/settings":
        await send_message(
            token,
            chat_id,
            "Settings: set bankroll (for sizing) and verbosity (full factor breakdown).",
            reply_markup=get_settings_keyboard(),
        )
        logger.info("command_handled", command="/settings", user_id=user_id)
    else:
        # Unknown command; optional: reply "Unknown command. /help"
        pass


async def _handle_callback(
    token: str,
    callback: dict[str, Any],
    allowed_ids: list[int],
) -> None:
    """Handle inline button callback: answer and optionally send message."""
    user_id = callback.get("from", {}).get("id")
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    callback_id = callback.get("id")
    data = (callback.get("data") or "").strip()
    if not user_id or user_id not in allowed_ids:
        if callback_id:
            await answer_callback(token, callback_id, "Unauthorized")
        return
    if not callback_id:
        return
    await answer_callback(token, callback_id)
    if chat_id is None:
        return
    if data == "detail":
        await handle_full_details(token, chat_id)
    elif (
        data
        in (
            "settings_bankroll",
            "settings_verbose",
            "settings_bet_size",
            "settings_kelly",
            "settings_back",
        )
        or data.startswith("bankroll_")
        or data.startswith("bet_size_")
        or data.startswith("kelly_")
        or data in ("verbose_on", "verbose_off")
    ):
        message = callback.get("message", {})
        edit_message_id = message.get("message_id") if message else None
        await handle_settings_callback(token, chat_id, user_id, data, edit_message_id)
