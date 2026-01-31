"""Persist feature snapshots for a signal run and query feature+outcome history."""

from datetime import date, datetime, timezone
from typing import Any

from app.db.session import acquire
from app.fetchers.registry import FeatureSnapshot
from app.logging_config import get_logger

logger = get_logger(__name__)


async def insert_snapshots(signal_run_id: int, snapshot: FeatureSnapshot) -> None:
    """Insert feature snapshot rows for the given signal_run_id."""
    rows = snapshot.to_rows()
    if not rows:
        return
    async with acquire() as conn:
        for row in rows:
            await conn.execute(
                """
                INSERT INTO feature_snapshots (signal_run_id, source_id, raw_value, normalized_score, stale)
                VALUES ($1, $2, $3, $4, $5)
                """,
                signal_run_id,
                row["source_id"],
                row.get("raw_value"),
                row.get("normalized_score"),
                row.get("stale", False),
            )
    logger.info("feature_snapshots_inserted", signal_run_id=signal_run_id, count=len(rows))


async def get_latest_data_source_status() -> list[dict[str, Any]]:
    """
    Return per-source status from the most recent signal run's feature snapshots.
    Each item: {source_id, status} where status is 'ok' | 'stale' | 'fail'.
    """
    async with acquire() as conn:
        run_id_row = await conn.fetchrow(
            "SELECT id FROM signal_runs ORDER BY run_at DESC LIMIT 1",
        )
        if run_id_row is None:
            return []
        run_id = run_id_row["id"]
        rows = await conn.fetch(
            """
            SELECT source_id, normalized_score, stale
            FROM feature_snapshots
            WHERE signal_run_id = $1
            ORDER BY source_id
            """,
            run_id,
        )
    out: list[dict[str, Any]] = []
    for r in rows:
        if r["stale"]:
            status = "stale"
        elif r["normalized_score"] is not None:
            status = "ok"
        else:
            status = "fail"
        out.append({"source_id": r["source_id"], "status": status})
    return out


async def fetch_resolved_runs_with_features(
    date_from: date,
    date_to: date,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    """
    Return resolved runs (WIN/LOSS) in [date_from, date_to] with their feature snapshot.
    One row per run per source: run_at, outcome, actual_result, model_p, signal_run_id,
    source_id, raw_value, normalized_score, stale. For backtest and feature-outcome analysis.
    """
    dt_from = datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc)
    dt_to = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc)
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sr.id AS signal_run_id, sr.run_at, sr.outcome, sr.actual_result,
                   sr.model_p, fs.source_id, fs.raw_value, fs.normalized_score, fs.stale
            FROM signal_runs sr
            JOIN feature_snapshots fs ON fs.signal_run_id = sr.id
            WHERE sr.outcome IN ('WIN', 'LOSS')
              AND sr.run_at >= $1 AND sr.run_at <= $2
            ORDER BY sr.run_at DESC, fs.source_id
            LIMIT $3
            """,
            dt_from,
            dt_to,
            limit,
        )
    return [dict(r) for r in rows]
