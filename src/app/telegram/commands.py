"""Telegram command handlers: /signal, /stats, /history."""

from datetime import datetime, timezone
from typing import Any

from app.analytics.calibration import calibration_error_text, calibration_summary
from app.analytics.drawdown import max_drawdown
from app.analytics.rolling import current_streak, rolling_win_rate
from app.config import get_settings
from app.db.feature_snapshots import insert_snapshots
from app.db.market_metadata import upsert_market_metadata
from app.db.session import acquire, get_pool
from app.db.user_prefs import ensure_user, get_user_prefs, set_user_prefs
from app.db.signal_runs import (
    ORDER_BOOK_SNAPSHOT_LEVELS,
    create_signal_run,
    get_existing_run_for_market_today,
    get_latest_run_id,
    get_run_result,
    update_signal_run_with_result,
)
from app.fetchers.registry import run_all_fetchers, run_fetchers_for_market
from app.logging_config import get_logger
from app.polymarket.client import fetch_order_book
from app.polymarket.depth import max_safe_size_usd
from app.polymarket.models import Market, MarketQuote, OrderBook, UpDownMarket
from app.polymarket.selection import (
    select_btc_market,
    select_btc_up_down_hourly_markets_next_n,
)
from app.polymarket.selection_15m import (
    build_updown_quote,
    select_btc_15m_updown_market,
)
from app.signal.engine import run_engine
from app.signal.engine_15m import Signal15mResult, fetch_klines_1m, run_engine_15m
from app.signal.reasoning import missing_sources as get_missing_sources
from app.signal.weights import get_weights
from app.telegram.formatter import (
    format_signal_message,
    format_signal_15m_summary,
    format_signal_multi_hour,
    _hour_label_from_slug,
)
from app.telegram.send import send_message
from app.signal.engine import SignalResult

logger = get_logger(__name__)


def _order_book_to_snapshot(book: OrderBook) -> dict[str, Any]:
    """Build JSON-serializable order book snapshot (top N levels) for paper-mode slippage audit."""
    from datetime import datetime, timezone

    n = ORDER_BOOK_SNAPSHOT_LEVELS
    bids = [{"price": lvl.price, "size": lvl.size} for lvl in (book.bids[:n] if book.bids else [])]
    asks = [{"price": lvl.price, "size": lvl.size} for lvl in (book.asks[:n] if book.asks else [])]
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bids": bids,
        "asks": asks,
    }


async def handle_signal(token: str, chat_id: int, user_id: int) -> None:
    """
    Phase 4: Full signal pipeline.
    Create run → run fetchers → persist snapshot → get market + quote → run engine →
    store result → send Telegram summary (direction, model_p, market_p, edge, rec bet, reasoning).
    Prefers next upcoming hourly Up/Down market; falls back to daily.
    """
    market: Market | None = await select_btc_market()
    if not market:
        # Analytical fallback: run fetchers + engine with synthetic quote so user gets a view
        settings = get_settings()
        await ensure_user(user_id)
        prefs = await get_user_prefs(user_id)
        bankroll = prefs["bankroll_usd"] if prefs else settings.default_bankroll_usd
        snapshot = await run_all_fetchers()
        weights = get_weights()
        synthetic_quote = MarketQuote(
            best_bid=0.5,
            best_ask=0.5,
            spread=0.0,
            implied_prob_yes=0.5,
            max_safe_size_usd=0.0,
        )
        max_bet = prefs.get("bet_size_usd") if prefs else None
        kelly_override = prefs.get("kelly_fraction_override") if prefs else None
        result = run_engine(
            snapshot,
            synthetic_quote,
            market_slug=None,
            market_condition_id=None,
            bankroll_usd=bankroll,
            weights=weights,
            max_bet_usd=max_bet,
            kelly_fraction_override=kelly_override,
        )
        missing_list = get_missing_sources(snapshot.results)
        msg = (
            "No active BTC market found (hourly Up/Down or daily).\n\n"
            "<b>Analytical view</b> (no market to trade; model vs 50% reference):\n\n"
            + format_signal_message(
                result,
                verbose=False,
                missing_sources=missing_list or None,
                market=None,
            )
        )
        await send_message(token, chat_id, msg)
        logger.info("signal_analytical_fallback", user_id=user_id)
        return

    now_utc = datetime.now(timezone.utc)
    existing_run_id = await get_existing_run_for_market_today(market.condition_id, now_utc)
    if existing_run_id is not None:
        result = await get_run_result(existing_run_id)
        if result:
            msg = format_signal_message(result, verbose=False, market=market)
            reply_markup: dict[str, Any] | None = None
            if market.slug:
                reply_markup = {
                    "inline_keyboard": [
                        [
                            {"text": "Full Details", "callback_data": "detail"},
                            {
                                "text": "Open Polymarket",
                                "url": f"https://polymarket.com/event/{market.slug}",
                            },
                        ],
                    ],
                }
            await send_message(token, chat_id, msg, reply_markup=reply_markup)
            logger.info(
                "command_handled",
                command="/signal",
                user_id=user_id,
                market_slug=market.slug,
                direction=result.direction,
                reused_run_id=existing_run_id,
            )
            return

    run_id = await create_signal_run(
        market_condition_id=market.condition_id,
        market_slug=market.slug,
    )
    snapshot, weights = await run_fetchers_for_market(market)
    await insert_snapshots(run_id, snapshot)  # persist raw inputs for reproducibility

    best_bid = market.best_bid
    best_ask = market.best_ask
    book: OrderBook | None = None
    used_gamma_fallback = False
    yes_token = market.clob_token_ids.strip() if market.clob_token_ids else None
    if yes_token:
        try:
            book = await fetch_order_book(yes_token)
            best_bid = book.best_bid or best_bid
            best_ask = book.best_ask or best_ask
        except Exception as e:
            logger.warning("signal_order_book_failed", error=str(e))
            used_gamma_fallback = True

    spread = (best_ask - best_bid) if (best_bid is not None and best_ask is not None) else 0.0
    best_ask_val = best_ask if best_ask is not None else 0.0
    max_safe = max_safe_size_usd(book, side="ask") if book else 0.0

    await upsert_market_metadata(
        condition_id=market.condition_id,
        slug=market.slug,
        resolution_source=market.resolution_source,
        end_date=market.end_date,
    )

    quote = MarketQuote(
        best_bid=best_bid or 0.0,
        best_ask=best_ask_val,
        spread=spread,
        implied_prob_yes=best_ask_val,
        max_safe_size_usd=max_safe,
    )

    settings = get_settings()
    await ensure_user(user_id)
    prefs = await get_user_prefs(user_id)
    bankroll = prefs["bankroll_usd"] if prefs else settings.default_bankroll_usd
    max_bet = prefs.get("bet_size_usd") if prefs else None
    kelly_override = prefs.get("kelly_fraction_override") if prefs else None
    result = run_engine(
        snapshot,
        quote,
        market_slug=market.slug,
        market_condition_id=market.condition_id,
        bankroll_usd=bankroll,
        weights=weights,
        max_bet_usd=max_bet,
        kelly_fraction_override=kelly_override,
    )
    if used_gamma_fallback:
        fallback_note = "Order book unavailable; using Gamma mid. "
        result.liquidity_warning = (result.liquidity_warning or "") + fallback_note
    order_book_snapshot: dict[str, Any] | None = None
    if settings.paper_trading and book is not None:
        order_book_snapshot = _order_book_to_snapshot(book)
    await update_signal_run_with_result(run_id, result, order_book_snapshot=order_book_snapshot)

    missing_list = get_missing_sources(snapshot.results)
    msg = format_signal_message(
        result, verbose=False, missing_sources=missing_list or None, market=market
    )
    reply_markup: dict[str, Any] | None = None
    if market.slug:
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "Full Details", "callback_data": "detail"},
                    {
                        "text": "Open Polymarket",
                        "url": f"https://polymarket.com/event/{market.slug}",
                    },
                ],
            ],
        }
    await send_message(token, chat_id, msg, reply_markup=reply_markup)
    logger.info(
        "command_handled",
        command="/signal",
        user_id=user_id,
        market_slug=market.slug,
        direction=result.direction,
    )


async def handle_signal_hourly5(token: str, chat_id: int, user_id: int) -> None:
    """
    Predict next 5 hourly BTC Up/Down markets so you can place bets up to 5 hours in advance.
    One snapshot (fetchers), then per-market quote + engine; single message with links to each.
    """
    markets = await select_btc_up_down_hourly_markets_next_n(n=5)
    if not markets:
        await send_message(
            token,
            chat_id,
            "No active BTC hourly Up/Down markets found for the next 5 hours.",
        )
        logger.info("signal_hourly5_no_markets", user_id=user_id)
        return

    settings = get_settings()
    await ensure_user(user_id)
    prefs = await get_user_prefs(user_id)
    bankroll = prefs["bankroll_usd"] if prefs else settings.default_bankroll_usd
    max_bet = prefs.get("bet_size_usd") if prefs else None
    kelly_override = prefs.get("kelly_fraction_override") if prefs else None

    snapshot, weights = await run_fetchers_for_market(markets[0])
    markets_results: list[tuple[Market, SignalResult]] = []

    for market in markets:
        best_bid = market.best_bid
        best_ask = market.best_ask
        book: OrderBook | None = None
        yes_token = market.clob_token_ids.strip() if market.clob_token_ids else None
        if yes_token:
            try:
                book = await fetch_order_book(yes_token)
                best_bid = book.best_bid or best_bid
                best_ask = book.best_ask or best_ask
            except Exception as e:
                logger.warning("hourly5_order_book_failed", slug=market.slug, error=str(e))
        spread = (best_ask - best_bid) if (best_bid is not None and best_ask is not None) else 0.0
        best_ask_val = best_ask if best_ask is not None else 0.5
        max_safe = max_safe_size_usd(book, side="ask") if book else 0.0
        quote = MarketQuote(
            best_bid=best_bid or 0.0,
            best_ask=best_ask_val,
            spread=spread,
            implied_prob_yes=best_ask_val,
            max_safe_size_usd=max_safe,
        )
        result = run_engine(
            snapshot,
            quote,
            market_slug=market.slug,
            market_condition_id=market.condition_id,
            bankroll_usd=bankroll,
            weights=weights,
            max_bet_usd=max_bet,
            kelly_fraction_override=kelly_override,
        )
        markets_results.append((market, result))

    missing_list = get_missing_sources(snapshot.results)
    msg = format_signal_multi_hour(markets_results, missing_sources=missing_list or None)

    reply_markup: dict[str, Any] | None = None
    if markets_results:
        keyboard = []
        for market, _ in markets_results:
            if market.slug:
                label = _hour_label_from_slug(market.slug)
                keyboard.append([
                    {
                        "text": f"Open {label}",
                        "url": f"https://polymarket.com/event/{market.slug}",
                    },
                ])
        if keyboard:
            reply_markup = {"inline_keyboard": keyboard}

    await send_message(token, chat_id, msg, reply_markup=reply_markup)
    logger.info(
        "command_handled",
        command="/hourly5",
        user_id=user_id,
        market_count=len(markets_results),
    )


def _signal_15m_result_to_signal_result(
    result_15m: Signal15mResult,
    market: UpDownMarket,
) -> SignalResult:
    """Convert Signal15mResult to SignalResult for DB storage (direction YES/NO/NO_TRADE)."""
    direction = "NO_TRADE"
    if result_15m.direction == "BUY_UP":
        direction = "YES"
    elif result_15m.direction == "BUY_DOWN":
        direction = "NO"
    edge = result_15m.edge_up if result_15m.direction == "BUY_UP" else result_15m.edge_down
    if edge is None:
        edge = result_15m.edge_up or result_15m.edge_down or 0.0
    reasoning_summary_parts = [
        f"{r.get('factor', '?')}={r.get('value', r.get('detail', '-'))}"
        for r in (result_15m.reasoning or [])
    ]
    reasoning_summary = ", ".join(reasoning_summary_parts) if reasoning_summary_parts else "-"
    return SignalResult(
        direction=direction,
        model_p=result_15m.model_up,
        market_p=result_15m.market_up_norm,
        edge=edge,
        recommended_usd=result_15m.recommended_usd,
        reasoning=result_15m.reasoning or [],
        reasoning_summary=reasoning_summary,
        liquidity_warning=result_15m.liquidity_warning,
        market_slug=market.slug,
        market_condition_id=market.condition_id,
    )


async def handle_signal_15m(token: str, chat_id: int, user_id: int) -> None:
    """
    BTC 15m Up/Down signal: select market by series_id, build quote, fetch 1m klines,
    run 15m engine, store to signal_runs, send Telegram summary.
    """
    market: UpDownMarket | None = await select_btc_15m_updown_market()
    if not market:
        await send_message(
            token,
            chat_id,
            "No active BTC 15m Up/Down market found.",
        )
        logger.info("signal_15m_no_market", user_id=user_id)
        return

    quote = await build_updown_quote(market)
    if not quote:
        await send_message(
            token,
            chat_id,
            "Could not fetch 15m market prices or order book.",
        )
        logger.warning("signal_15m_quote_failed", user_id=user_id)
        return

    now_utc = datetime.now(timezone.utc)
    remaining_minutes: float | None = None
    if market.end_date:
        try:
            from datetime import datetime as dt

            end_dt = dt.fromisoformat(market.end_date.replace("Z", "+00:00"))
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            remaining_minutes = max(0.0, (end_dt - now_utc).total_seconds() / 60.0)
        except (ValueError, TypeError):
            remaining_minutes = 15.0

    candles_1m = await fetch_klines_1m(limit=240)
    settings = get_settings()
    await ensure_user(user_id)
    prefs = await get_user_prefs(user_id)
    bankroll = prefs["bankroll_usd"] if prefs else settings.default_bankroll_usd

    result_15m = run_engine_15m(
        quote=quote,
        remaining_minutes=remaining_minutes,
        bankroll_usd=bankroll,
        candles_1m=candles_1m,
    )

    run_id = await create_signal_run(
        market_condition_id=market.condition_id,
        market_slug=market.slug,
    )
    signal_result = _signal_15m_result_to_signal_result(result_15m, market)
    await update_signal_run_with_result(run_id, signal_result)

    from app.db.market_metadata import upsert_market_metadata

    await upsert_market_metadata(
        condition_id=market.condition_id,
        slug=market.slug,
        resolution_source=market.resolution_source,
        end_date=market.end_date,
    )

    msg = format_signal_15m_summary(result_15m, market_slug=market.slug)
    reply_markup: dict[str, Any] | None = None
    if market.slug:
        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "Open Polymarket",
                        "url": f"https://polymarket.com/event/{market.slug}",
                    },
                ],
            ],
        }
    await send_message(token, chat_id, msg, reply_markup=reply_markup)
    logger.info(
        "command_handled",
        command="/signal15m",
        user_id=user_id,
        market_slug=market.slug,
        direction=result_15m.direction,
    )


async def handle_stats(token: str, chat_id: int, user_id: int) -> None:
    """Win rate (last 30), calibration summary, current streak, max drawdown, last N outcomes."""
    pool = get_pool()
    if pool is None:
        await send_message(token, chat_id, "DB unavailable. Cannot show stats.")
        return
    try:
        win = await rolling_win_rate(30)
        streak = await current_streak()
        cal = await calibration_summary()
        cal_text = calibration_error_text(cal)
        dd = await max_drawdown(100)
        # Last N outcomes (e.g. 5) for quick glance
        last_n = 5
        async with acquire() as conn:
            outcome_rows = await conn.fetch(
                """
                SELECT outcome FROM signal_runs
                WHERE outcome IS NOT NULL
                ORDER BY resolved_at DESC NULLS LAST, run_at DESC
                LIMIT $1
                """,
                last_n,
            )
        outcome_chars = []
        for r in outcome_rows:
            o = r["outcome"]
            if o == "WIN":
                outcome_chars.append("W")
            elif o == "LOSS":
                outcome_chars.append("L")
            else:
                outcome_chars.append("-")
        last_outcomes = " ".join(outcome_chars) if outcome_chars else "-"
    except Exception as e:
        logger.warning("stats_failed", error=str(e))
        await send_message(token, chat_id, f"Stats error: {e}")
        return
    msg = (
        f"<b>Stats (last 30)</b>\n"
        f"Win rate: {win['win_rate']:.0%} ({win['wins']}W / {win['losses']}L)\n"
        f"Streak: {streak}\n"
        f"Max drawdown: {dd} losses\n"
        f"Calibration: {cal_text}\n"
        f"Last {last_n}: {last_outcomes}"
    )
    await send_message(token, chat_id, msg)
    logger.info("command_handled", command="/stats", user_id=user_id)


async def handle_history(token: str, chat_id: int, user_id: int, n: int) -> None:
    """Last n signals with outcome (WIN/LOSS/SKIP)."""
    pool = get_pool()
    if pool is None:
        await send_message(token, chat_id, "DB unavailable. Cannot show history.")
        return
    try:
        async with acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT run_at, direction, outcome, model_p
                FROM signal_runs
                ORDER BY run_at DESC
                LIMIT $1
                """,
                n,
            )
    except Exception as e:
        logger.warning("history_failed", error=str(e))
        await send_message(token, chat_id, f"History error: {e}")
        return
    if not rows:
        await send_message(token, chat_id, "No signals yet.")
        return
    lines = []
    for r in rows:
        run_at = r["run_at"].strftime("%Y-%m-%d") if r["run_at"] else "?"
        direction = r["direction"] or "?"
        outcome = r["outcome"] or "-"
        model_p = f"{float(r['model_p']):.0%}" if r["model_p"] is not None else "-"
        lines.append(f"{run_at} {direction} {outcome} ({model_p})")
    msg = "<b>Last " + str(n) + " signals</b>\n" + "\n".join(lines)
    if len(msg) > 4000:
        msg = msg[:3990] + "\n..."
    await send_message(token, chat_id, msg)
    logger.info("command_handled", command="/history", user_id=user_id)


async def handle_full_details(token: str, chat_id: int) -> None:
    """Send verbose factor breakdown from the latest signal run, or prompt to run /signal."""
    latest_id = await get_latest_run_id()
    if latest_id is None:
        await send_message(
            token,
            chat_id,
            "No signal yet. Run /signal first to get today's signal, then use Full Details.",
        )
        return
    result = await get_run_result(latest_id)
    if not result:
        await send_message(token, chat_id, "Could not load last signal.")
        return
    msg = format_signal_message(result, verbose=True)
    await send_message(token, chat_id, msg)
    logger.info("full_details_sent", chat_id=chat_id, run_id=latest_id)


def get_settings_keyboard() -> dict[str, Any]:
    """Inline keyboard for /settings: bankroll, bet size, Kelly fraction, verbosity, Back."""
    return {
        "inline_keyboard": [
            [
                {"text": "Set bankroll", "callback_data": "settings_bankroll"},
                {"text": "Set bet size", "callback_data": "settings_bet_size"},
            ],
            [
                {"text": "Set Kelly %", "callback_data": "settings_kelly"},
                {"text": "Set verbosity", "callback_data": "settings_verbose"},
            ],
            [{"text": "Back", "callback_data": "settings_back"}],
        ],
    }


def get_bankroll_keyboard() -> dict[str, Any]:
    """Inline keyboard for bankroll presets (USD)."""
    return {
        "inline_keyboard": [
            [
                {"text": "$500", "callback_data": "bankroll_500"},
                {"text": "$1000", "callback_data": "bankroll_1000"},
                {"text": "$2000", "callback_data": "bankroll_2000"},
                {"text": "$5000", "callback_data": "bankroll_5000"},
            ],
            [{"text": "Back", "callback_data": "settings_back"}],
        ],
    }


def get_bet_size_keyboard() -> dict[str, Any]:
    """Inline keyboard for max bet size (USD); caps Kelly recommendation."""
    return {
        "inline_keyboard": [
            [
                {"text": "$25", "callback_data": "bet_size_25"},
                {"text": "$50", "callback_data": "bet_size_50"},
                {"text": "$100", "callback_data": "bet_size_100"},
                {"text": "$200", "callback_data": "bet_size_200"},
            ],
            [
                {"text": "Clear cap", "callback_data": "bet_size_clear"},
                {"text": "Back", "callback_data": "settings_back"},
            ],
        ],
    }


def get_kelly_keyboard() -> dict[str, Any]:
    """Inline keyboard for Kelly fraction override (e.g. 0.25 = quarter Kelly)."""
    return {
        "inline_keyboard": [
            [
                {"text": "25%", "callback_data": "kelly_25"},
                {"text": "50%", "callback_data": "kelly_50"},
                {"text": "100%", "callback_data": "kelly_100"},
            ],
            [
                {"text": "Use default", "callback_data": "kelly_clear"},
                {"text": "Back", "callback_data": "settings_back"},
            ],
        ],
    }


def get_verbose_keyboard() -> dict[str, Any]:
    """Inline keyboard for verbose On/Off."""
    return {
        "inline_keyboard": [
            [
                {"text": "On", "callback_data": "verbose_on"},
                {"text": "Off", "callback_data": "verbose_off"},
            ],
            [{"text": "Back", "callback_data": "settings_back"}],
        ],
    }


async def handle_settings_callback(
    token: str,
    chat_id: int,
    user_id: int,
    data: str,
    edit_message_id: int | None,
) -> None:
    """
    Handle settings-related callback_data: settings_bankroll, settings_verbose,
    bankroll_500, verbose_on, verbose_off, settings_back.
    """
    await ensure_user(user_id)
    if data == "settings_bankroll":
        await send_message(
            token,
            chat_id,
            "Choose bankroll (USD) for sizing:",
            reply_markup=get_bankroll_keyboard(),
        )
    elif data == "settings_bet_size":
        await send_message(
            token,
            chat_id,
            "Choose max bet size (USD). Kelly recommendation will be capped by this.",
            reply_markup=get_bet_size_keyboard(),
        )
    elif data == "settings_kelly":
        await send_message(
            token,
            chat_id,
            "Choose Kelly fraction (full Kelly = 100%). Lower is more conservative.",
            reply_markup=get_kelly_keyboard(),
        )
    elif data == "settings_verbose":
        await send_message(
            token,
            chat_id,
            "Verbose mode: show full factor breakdown in signals.",
            reply_markup=get_verbose_keyboard(),
        )
    elif data.startswith("bankroll_"):
        try:
            amount = int(data.replace("bankroll_", ""))
            if amount > 0:
                await set_user_prefs(user_id, bankroll_usd=float(amount))
                await send_message(token, chat_id, f"Bankroll set to ${amount}.")
        except ValueError:
            pass
    elif data.startswith("bet_size_"):
        if data == "bet_size_clear":
            await set_user_prefs(user_id, clear_bet_size_usd=True)
            await send_message(token, chat_id, "Bet size cap cleared. Using full Kelly (subject to config).")
        else:
            try:
                amount = int(data.replace("bet_size_", ""))
                if amount > 0:
                    await set_user_prefs(user_id, bet_size_usd=float(amount))
                    await send_message(token, chat_id, f"Max bet set to ${amount}.")
            except ValueError:
                pass
    elif data.startswith("kelly_"):
        if data == "kelly_clear":
            await set_user_prefs(user_id, clear_kelly_fraction_override=True)
            await send_message(token, chat_id, "Kelly: using default from config.")
        else:
            mapping = {"kelly_25": 0.25, "kelly_50": 0.5, "kelly_100": 1.0}
            frac = mapping.get(data)
            if frac is not None:
                await set_user_prefs(user_id, kelly_fraction_override=frac)
                await send_message(token, chat_id, f"Kelly fraction set to {frac:.0%}.")
    elif data == "verbose_on":
        await set_user_prefs(user_id, verbose=True)
        await send_message(token, chat_id, "Verbose mode: On.")
    elif data == "verbose_off":
        await set_user_prefs(user_id, verbose=False)
        await send_message(token, chat_id, "Verbose mode: Off.")
    elif data == "settings_back":
        await send_message(token, chat_id, "Settings closed.")
    logger.info("settings_callback_handled", user_id=user_id, data=data)


async def run_daily_signal_broadcast() -> dict[str, Any]:
    """
    Run the daily signal pipeline once and send the formatted message to all allowed users.
    Idempotent per day: reuses existing run if already generated for today's market.
    Returns {"ok": bool, "signal_sent": bool, "reason": str, "recipients": int}.
    """
    settings = get_settings()
    token = settings.telegram_bot_token
    user_ids = settings.allowed_user_ids_list()
    if not user_ids:
        return {"ok": True, "signal_sent": False, "reason": "no_allowed_users", "recipients": 0}

    market = await select_btc_market()
    if not market:
        return {"ok": True, "signal_sent": False, "reason": "no_market", "recipients": 0}

    now_utc = datetime.now(timezone.utc)
    existing_run_id = await get_existing_run_for_market_today(market.condition_id, now_utc)
    if existing_run_id is not None:
        result = await get_run_result(existing_run_id)
        if not result:
            return {
                "ok": True,
                "signal_sent": False,
                "reason": "reused_run_unreadable",
                "recipients": 0,
            }
        msg = format_signal_message(result, verbose=False, market=market)
        reply_markup: dict[str, Any] | None = None
        if market.slug:
            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "Full Details", "callback_data": "detail"},
                        {
                            "text": "Open Polymarket",
                            "url": f"https://polymarket.com/event/{market.slug}",
                        },
                    ],
                ],
            }
        for uid in user_ids:
            try:
                await send_message(token, int(uid), msg, reply_markup=reply_markup)
            except Exception as e:
                logger.warning("daily_signal_send_failed", user_id=uid, error=str(e))
        return {"ok": True, "signal_sent": True, "reason": "reused", "recipients": len(user_ids)}
    # Create new run
    run_id = await create_signal_run(
        market_condition_id=market.condition_id,
        market_slug=market.slug,
    )
    snapshot, weights = await run_fetchers_for_market(market)
    await insert_snapshots(run_id, snapshot)

    best_bid = market.best_bid
    best_ask = market.best_ask
    book: OrderBook | None = None
    yes_token = market.clob_token_ids.strip() if market.clob_token_ids else None
    if yes_token:
        try:
            book = await fetch_order_book(yes_token)
            best_bid = book.best_bid or best_bid
            best_ask = book.best_ask or best_ask
        except Exception as e:
            logger.warning("signal_order_book_failed", error=str(e))

    spread = (best_ask - best_bid) if (best_bid is not None and best_ask is not None) else 0.0
    best_ask_val = best_ask if best_ask is not None else 0.0
    max_safe = max_safe_size_usd(book, side="ask") if book else 0.0
    await upsert_market_metadata(
        condition_id=market.condition_id,
        slug=market.slug,
        resolution_source=market.resolution_source,
        end_date=market.end_date,
    )
    quote = MarketQuote(
        best_bid=best_bid or 0.0,
        best_ask=best_ask_val,
        spread=spread,
        implied_prob_yes=best_ask_val,
        max_safe_size_usd=max_safe,
    )
    bankroll = settings.default_bankroll_usd
    result = run_engine(
        snapshot,
        quote,
        market_slug=market.slug,
        market_condition_id=market.condition_id,
        bankroll_usd=bankroll,
        weights=weights,
    )
    order_book_snapshot = _order_book_to_snapshot(book) if settings.paper_trading and book else None
    await update_signal_run_with_result(run_id, result, order_book_snapshot=order_book_snapshot)

    msg = format_signal_message(result, verbose=False, market=market)
    reply_markup = None
    if market.slug:
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "Full Details", "callback_data": "detail"},
                    {
                        "text": "Open Polymarket",
                        "url": f"https://polymarket.com/event/{market.slug}",
                    },
                ],
            ],
        }
    for uid in user_ids:
        try:
            await send_message(token, int(uid), msg, reply_markup=reply_markup)
        except Exception as e:
            logger.warning("daily_signal_send_failed", user_id=uid, error=str(e))
    return {"ok": True, "signal_sent": True, "reason": "created", "recipients": len(user_ids)}
