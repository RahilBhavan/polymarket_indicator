"""FastAPI app: health, webhook (Telegram). Verify secret; whitelist users."""

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db.session import close_pool, health_check, init_pool
from app.logging_config import configure_logging, get_logger
from app.telegram.admin import send_admin_alert
from app.telegram.handler import handle_update
from app.telegram.webhook import verify_telegram_webhook

configure_logging(debug=False)
logger = get_logger(__name__)


def validate_startup_config() -> None:
    """
    Validate critical configuration on startup.
    Exits with error code 1 if validation fails.
    """
    # Add scripts to path for validation import
    project_root = Path(__file__).parent.parent.parent
    scripts_path = project_root / "scripts"
    sys.path.insert(0, str(scripts_path))

    try:
        from validate_env import validate_env, ValidationError

        # Validate required environment variables
        try:
            validate_env(mode="required")
            logger.info("startup_validation_passed", msg="Environment configuration validated")
        except ValidationError as e:
            logger.error("startup_validation_failed", error=str(e))
            print(f"\n❌ Startup validation failed: {e}\n", file=sys.stderr)
            print("Fix the errors in your .env file and restart.\n", file=sys.stderr)
            print("Run this to validate manually:", file=sys.stderr)
            print("  uv run python scripts/validate_env.py\n", file=sys.stderr)
            sys.exit(1)
    except ImportError:
        # Validation script not available, log warning and continue
        logger.warning(
            "startup_validation_skipped",
            msg="validate_env.py not found, skipping startup validation"
        )
    finally:
        # Clean up path
        if str(scripts_path) in sys.path:
            sys.path.remove(str(scripts_path))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: validate config, init DB pool (optional; app runs even if DB down).
    Shutdown: close pool.
    """
    # Validate configuration before starting
    validate_startup_config()

    # Initialize database pool
    await init_pool()

    # Check production configuration
    settings = get_settings()
    if settings.env == "production":
        if settings.eod_cron_secret is None:
            logger.warning(
                "eod_cron_secret_unset_in_production",
                msg="EOD_CRON_SECRET should be set in production"
            )
        if settings.admin_chat_id is None:
            logger.warning(
                "admin_chat_id_unset_in_production",
                msg="ADMIN_CHAT_ID recommended for production error alerts"
            )

    logger.info("startup_complete", msg="CryptoSignal bot started successfully")

    try:
        yield
    finally:
        logger.info("shutdown_starting", msg="Shutting down CryptoSignal bot")
        try:
            await close_pool()
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise  # Preserve Ctrl+C / SIGINT so process exits cleanly
        except Exception:
            logger.exception("lifespan_shutdown_error")


app = FastAPI(title="CryptoSignal Bot", lifespan=lifespan)


@app.get("/health")
async def health() -> JSONResponse:
    """Health check for uptime monitoring. 503 if DB down. Includes last_signal_at and data_sources when DB is up."""
    db_ok = await health_check()
    if not db_ok:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "db": "disconnected"},
        )
    from app.db.feature_snapshots import get_latest_data_source_status
    from app.db.signal_runs import get_last_signal_at

    last_signal_at = await get_last_signal_at()
    data_sources = await get_latest_data_source_status()
    content: dict[str, Any] = {
        "status": "ok",
        "db": "connected",
        "last_signal_at": last_signal_at,
        "data_sources": data_sources,
    }
    return JSONResponse(status_code=200, content=content)


@app.post("/internal/run-daily-signal")
async def run_daily_signal(request: Request) -> JSONResponse:
    """
    Cron: run daily signal pipeline and send to all allowed users.
    Idempotent per day: reuses existing run if already generated. Protected by X-Cron-Secret (same as EOD).
    """
    from app.telegram.commands import run_daily_signal_broadcast

    settings = get_settings()
    if settings.eod_cron_secret is None:
        return JSONResponse(
            status_code=403,
            content={"error": "EOD_CRON_SECRET required (use for X-Cron-Secret)"},
        )
    secret = request.headers.get("X-Cron-Secret")
    if secret != settings.eod_cron_secret:
        return JSONResponse(
            status_code=403,
            content={"error": "missing or invalid X-Cron-Secret"},
        )
    try:
        result = await run_daily_signal_broadcast()
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        logger.exception("daily_signal_error")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@app.post("/internal/run-eod-outcomes")
async def run_eod_outcomes(request: Request) -> JSONResponse:
    """
    Phase 5: EOD job. Resolve outcomes for signal runs whose market has ended.
    Call after 00:00 UTC (e.g. cron). EOD_CRON_SECRET required: set in env and
    send X-Cron-Secret header. When unset, returns 403.
    """
    from app.outcomes.recorder import run_eod_outcomes as run_eod

    settings = get_settings()
    if settings.eod_cron_secret is None:
        return JSONResponse(
            status_code=403,
            content={"error": "EOD_CRON_SECRET required"},
        )
    secret = request.headers.get("X-Cron-Secret")
    if secret != settings.eod_cron_secret:
        return JSONResponse(
            status_code=403,
            content={"error": "missing or invalid X-Cron-Secret"},
        )
    try:
        result = await run_eod()
        return JSONResponse(
            status_code=200,
            content={"ok": True, "updated": result["updated"], "failed": result["failed"]},
        )
    except Exception as e:
        logger.exception("eod_outcomes_error")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@app.post("/internal/admin-heartbeat")
async def admin_heartbeat(request: Request) -> JSONResponse:
    """
    Cron: send short heartbeat to ADMIN_CHAT_ID (e.g. "Last signal at X, direction Y").
    Protected by X-Cron-Secret. No-op if ADMIN_CHAT_ID or EOD_CRON_SECRET unset.
    """
    from app.db.signal_runs import get_last_signal_at
    from app.telegram.admin import send_admin_alert

    settings = get_settings()
    if not settings.admin_chat_id or not settings.eod_cron_secret:
        return JSONResponse(
            status_code=200,
            content={"ok": True, "skipped": "ADMIN_CHAT_ID or EOD_CRON_SECRET unset"},
        )
    secret = request.headers.get("X-Cron-Secret")
    if secret != settings.eod_cron_secret:
        return JSONResponse(
            status_code=403,
            content={"error": "missing or invalid X-Cron-Secret"},
        )
    last_at = await get_last_signal_at()
    if last_at:
        # Optional: fetch last run direction from DB for richer message
        from app.db.session import acquire

        async with acquire() as conn:
            row = await conn.fetchrow(
                "SELECT direction FROM signal_runs ORDER BY run_at DESC LIMIT 1",
            )
        direction = row["direction"] if row else "?"
        msg = f"CryptoSignal heartbeat: last signal at {last_at}, direction {direction}"
    else:
        msg = "CryptoSignal heartbeat: no signals yet."
    await send_admin_alert(msg)
    return JSONResponse(status_code=200, content={"ok": True, "sent": True})


@app.get("/api/signals")
async def api_signals(request: Request, limit: int = 20) -> JSONResponse:
    """Read-only: last N signal runs. Requires X-Cron-Secret (same as EOD)."""
    settings = get_settings()
    if (
        settings.eod_cron_secret
        and request.headers.get("X-Cron-Secret") != settings.eod_cron_secret
    ):
        return JSONResponse(status_code=403, content={"error": "missing or invalid X-Cron-Secret"})
    from app.db.session import acquire

    limit = min(100, max(1, limit))
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, run_at, market_slug, direction, model_p, market_p, edge, recommended_usd, outcome
            FROM signal_runs
            ORDER BY run_at DESC
            LIMIT $1
            """,
            limit,
        )
    out = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "run_at": r["run_at"].isoformat() if r["run_at"] else None,
                "market_slug": r["market_slug"],
                "direction": r["direction"],
                "model_p": float(r["model_p"]) if r["model_p"] is not None else None,
                "market_p": float(r["market_p"]) if r["market_p"] is not None else None,
                "edge": float(r["edge"]) if r["edge"] is not None else None,
                "recommended_usd": float(r["recommended_usd"])
                if r["recommended_usd"] is not None
                else None,
                "outcome": r["outcome"],
            }
        )
    return JSONResponse(status_code=200, content={"signals": out})


@app.get("/api/stats")
async def api_stats(request: Request) -> JSONResponse:
    """Read-only: win rate (last 30), streak, max drawdown. Requires X-Cron-Secret."""
    settings = get_settings()
    if (
        settings.eod_cron_secret
        and request.headers.get("X-Cron-Secret") != settings.eod_cron_secret
    ):
        return JSONResponse(status_code=403, content={"error": "missing or invalid X-Cron-Secret"})
    from app.analytics.calibration import calibration_summary
    from app.analytics.drawdown import max_drawdown
    from app.analytics.rolling import current_streak, rolling_win_rate

    win = await rolling_win_rate(30)
    streak = await current_streak()
    dd = await max_drawdown(100)
    cal = await calibration_summary()
    return JSONResponse(
        status_code=200,
        content={
            "win_rate_30": win,
            "current_streak": streak,
            "max_drawdown": dd,
            "calibration": cal,
        },
    )


@app.get("/api/15m-snapshot")
async def api_15m_snapshot(request: Request) -> JSONResponse:
    """
    Current BTC 15m Up/Down market + quote + remaining_minutes.
    Optional: last stored signal for this market. For console dashboard consumption.
    When EOD_CRON_SECRET is set, requires X-Cron-Secret header.
    """
    settings = get_settings()
    if (
        settings.eod_cron_secret
        and request.headers.get("X-Cron-Secret") != settings.eod_cron_secret
    ):
        return JSONResponse(status_code=403, content={"error": "missing or invalid X-Cron-Secret"})
    from datetime import datetime, timezone

    from app.polymarket.selection_15m import build_updown_quote, select_btc_15m_updown_market

    market = await select_btc_15m_updown_market()
    if not market:
        return JSONResponse(
            status_code=200,
            content={"ok": False, "reason": "no_market", "market": None, "quote": None},
        )
    quote = await build_updown_quote(market)
    if not quote:
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "reason": "quote_failed",
                "market": {"slug": market.slug, "condition_id": market.condition_id},
                "quote": None,
            },
        )
    now_utc = datetime.now(timezone.utc)
    remaining_minutes: float | None = None
    if market.end_date:
        try:
            end_dt = datetime.fromisoformat(market.end_date.replace("Z", "+00:00"))
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            remaining_minutes = max(0.0, (end_dt - now_utc).total_seconds() / 60.0)
        except (ValueError, TypeError):
            remaining_minutes = 15.0
    last_signal: dict[str, Any] | None = None
    try:
        from app.db.session import acquire

        async with acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT direction, model_p, market_p, edge, recommended_usd, run_at
                FROM signal_runs
                WHERE market_condition_id = $1 AND status = 'ok'
                ORDER BY run_at DESC
                LIMIT 1
                """,
                market.condition_id,
            )
        if row:
            last_signal = {
                "direction": row["direction"],
                "model_p": float(row["model_p"]) if row["model_p"] is not None else None,
                "market_p": float(row["market_p"]) if row["market_p"] is not None else None,
                "edge": float(row["edge"]) if row["edge"] is not None else None,
                "recommended_usd": float(row["recommended_usd"])
                if row["recommended_usd"] is not None
                else None,
                "run_at": row["run_at"].isoformat() if row["run_at"] else None,
            }
    except Exception:
        pass
    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "market": {
                "slug": market.slug,
                "condition_id": market.condition_id,
                "end_date": market.end_date,
                "remaining_minutes": remaining_minutes,
            },
            "quote": {
                "up_buy_price": quote.up_buy_price,
                "down_buy_price": quote.down_buy_price,
                "market_up_norm": quote.market_up_norm,
                "market_down_norm": quote.market_down_norm,
                "max_safe_up_usd": quote.max_safe_up_usd,
                "max_safe_down_usd": quote.max_safe_down_usd,
            },
            "last_signal": last_signal,
        },
    )


@app.get("/api/live-data")
async def api_live_data(request: Request) -> JSONResponse:
    """
    Fetch live data from all configured sources (ETF flows, price/MA, funding, DXY, etc.)
    and return raw + normalized values for analysis. Same data used by the signal engine.
    When EOD_CRON_SECRET is set, requires X-Cron-Secret header.
    """
    settings = get_settings()
    if (
        settings.eod_cron_secret
        and request.headers.get("X-Cron-Secret") != settings.eod_cron_secret
    ):
        return JSONResponse(status_code=403, content={"error": "missing or invalid X-Cron-Secret"})
    from app.fetchers.registry import run_all_fetchers

    snapshot = await run_all_fetchers()
    sources = [
        {
            "source_id": r.source_id,
            "raw_value": r.raw_value,
            "normalized_score": r.normalized_score,
            "stale": r.stale,
            "error": r.error,
        }
        for r in snapshot.results
    ]
    return JSONResponse(
        status_code=200,
        content={"timestamp": snapshot.timestamp, "sources": sources},
    )


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> JSONResponse:
    """
    Telegram webhook. Verify X-Telegram-Bot-Api-Secret-Token; then process Update.
    Returns 403 if secret missing or wrong. Returns 503 on handler or DB failure so Telegram retries.
    """
    verify_telegram_webhook(request)
    body: dict[str, Any] = await request.json()
    db_ok = await health_check()
    if not db_ok:
        return JSONResponse(
            status_code=503,
            content={"ok": "false", "error": "db_unavailable"},
        )
    try:
        await handle_update(body)
        return JSONResponse(status_code=200, content={"ok": "true"})
    except Exception as e:
        logger.exception("webhook_handler_error")
        await send_admin_alert(f"CryptoSignal error: {type(e).__name__} at webhook")
        return JSONResponse(
            status_code=503,
            content={"ok": "false", "error": "handler_error"},
        )
