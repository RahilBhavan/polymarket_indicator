"""Insert and update signal_runs."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import asyncpg

from app.db.session import acquire
from app.logging_config import get_logger
from app.signal.engine import SignalResult
from app.signal.reasoning import reasoning_summary

# Top N levels to store in order_book_snapshot (paper mode)
ORDER_BOOK_SNAPSHOT_LEVELS = 20

logger = get_logger(__name__)


async def fetch_resolved_outcomes(
    limit: int | None = None,
    columns: str = "outcome",
    extra_and: str | None = None,
    extra_args: tuple[Any, ...] = (),
) -> list[asyncpg.Record]:
    """
    Resolved runs (WIN/LOSS only), standard order. Optional limit and extra AND clause.
    """
    where = "WHERE outcome IN ('WIN', 'LOSS')"
    if extra_and:
        where += f" AND {extra_and}"
    order = "ORDER BY resolved_at DESC NULLS LAST, run_at DESC"
    sql = f"SELECT {columns} FROM signal_runs {where} {order}"
    args: list[Any] = list(extra_args)
    if limit is not None:
        sql += f" LIMIT ${len(args) + 1}"
        args.append(limit)
    async with acquire() as conn:
        return await conn.fetch(sql, *args)


async def get_existing_run_for_market_today(
    market_condition_id: str,
    run_at_utc: datetime,
) -> int | None:
    """
    Return run id if a completed run exists for this market and UTC date.
    Used to reuse today's signal instead of creating a duplicate run.
    """
    if run_at_utc.tzinfo is None:
        run_at_utc = run_at_utc.replace(tzinfo=timezone.utc)
    run_date = run_at_utc.date()
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id FROM signal_runs
            WHERE market_condition_id = $1
              AND (run_at AT TIME ZONE 'UTC')::date = $2
              AND status = 'ok'
            ORDER BY run_at DESC
            LIMIT 1
            """,
            market_condition_id,
            run_date,
        )
    return int(row["id"]) if row else None


async def get_run_result(run_id: int) -> SignalResult | None:
    """Load stored signal run as SignalResult for display (e.g. re-send today's signal)."""
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT direction, model_p, market_p, edge, recommended_usd,
                   reasoning_json, liquidity_warning, market_slug, market_condition_id
            FROM signal_runs
            WHERE id = $1 AND status = 'ok'
            """,
            run_id,
        )
    if not row:
        return None
    reasoning = row["reasoning_json"] or []
    summary = reasoning_summary(reasoning, missing_sources_list=None)
    return SignalResult(
        direction=row["direction"] or "NO_TRADE",
        model_p=float(row["model_p"]) if row["model_p"] is not None else 0.5,
        market_p=float(row["market_p"]) if row["market_p"] is not None else 0.5,
        edge=float(row["edge"]) if row["edge"] is not None else 0.0,
        recommended_usd=float(row["recommended_usd"])
        if row["recommended_usd"] is not None
        else 0.0,
        reasoning=reasoning,
        reasoning_summary=summary,
        liquidity_warning=row["liquidity_warning"],
        market_slug=row["market_slug"],
        market_condition_id=row["market_condition_id"],
    )


async def create_signal_run(
    run_at: datetime | None = None,
    market_condition_id: str | None = None,
    market_slug: str | None = None,
    asset: str = "btc",
) -> int:
    """Insert a new signal_run with status 'pending'; return id."""
    run_at = run_at or datetime.now(timezone.utc)
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO signal_runs (run_at, direction, status, market_condition_id, market_slug, asset)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            run_at,
            "NO_TRADE",
            "pending",
            market_condition_id,
            market_slug,
            asset,
        )
    return row["id"]


async def update_signal_run_with_result(
    signal_run_id: int,
    result: SignalResult,
    order_book_snapshot: dict[str, Any] | None = None,
) -> None:
    """Update signal_run with engine result. Optionally store order book snapshot (paper mode)."""
    async with acquire() as conn:
        await conn.execute(
            """
            UPDATE signal_runs
            SET market_slug = $1, market_condition_id = $2, direction = $3,
                model_p = $4, market_p = $5, edge = $6, recommended_usd = $7,
                reasoning_json = $8, liquidity_warning = $9, status = $10,
                order_book_snapshot = $11
            WHERE id = $12
            """,
            result.market_slug,
            result.market_condition_id,
            result.direction,
            Decimal(str(result.model_p)),
            Decimal(str(result.market_p)),
            Decimal(str(result.edge)),
            Decimal(str(result.recommended_usd)),
            result.reasoning,
            result.liquidity_warning,
            "ok",
            order_book_snapshot,
            signal_run_id,
        )
    logger.info("signal_run_updated", signal_run_id=signal_run_id, direction=result.direction)


async def get_latest_run_id() -> int | None:
    """Return id of the most recent completed signal run (status = 'ok'), or None."""
    async with acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM signal_runs WHERE status = 'ok' ORDER BY run_at DESC LIMIT 1",
        )
    return int(row["id"]) if row else None


async def get_last_signal_at() -> str | None:
    """Return ISO timestamp of most recent signal run (max run_at), or None if no runs."""
    async with acquire() as conn:
        row = await conn.fetchrow(
            "SELECT MAX(run_at) AS last_at FROM signal_runs",
        )
    if row is None or row["last_at"] is None:
        return None
    val = row["last_at"]
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)
