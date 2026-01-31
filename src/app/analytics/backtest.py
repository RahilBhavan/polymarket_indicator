"""Backtest: win rate, calibration, drawdown over a date range of resolved signal runs."""

from datetime import date, datetime, timezone
from typing import Any

from app.db.signal_runs import fetch_resolved_outcomes
from app.logging_config import get_logger

logger = get_logger(__name__)


async def backtest_date_range(
    date_from: date,
    date_to: date,
    bucket_size: float = 0.1,
) -> dict[str, Any]:
    """
    Compute backtest metrics over resolved runs in [date_from, date_to] (inclusive).
    Uses run_at for filtering. Returns wins, losses, win_rate, calibration buckets, max_drawdown.
    """
    dt_from = datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc)
    dt_to = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc)
    rows = await fetch_resolved_outcomes(
        limit=5000,
        columns="model_p, outcome, run_at",
        extra_and="run_at >= $1 AND run_at <= $2",
        extra_args=(dt_from, dt_to),
    )
    if not rows:
        return {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "runs": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "calibration": [],
            "max_drawdown": 0,
        }
    wins = sum(1 for r in rows if r["outcome"] == "WIN")
    losses = sum(1 for r in rows if r["outcome"] == "LOSS")
    total = len(rows)
    win_rate = wins / total if total else 0.0

    # Calibration by bucket
    buckets: dict[tuple[float, float], list[str]] = {}
    for r in rows:
        p = float(r["model_p"]) if r["model_p"] is not None else 0.5
        low = int(p / bucket_size) * bucket_size
        high = low + bucket_size
        key = (low, high)
        buckets.setdefault(key, []).append(r["outcome"])
    calibration = []
    for (low, high), outcomes in sorted(buckets.items()):
        b_wins = sum(1 for o in outcomes if o == "WIN")
        b_total = len(outcomes)
        calibration.append(
            {
                "bucket_low": low,
                "bucket_high": high,
                "predicted": round((low + high) / 2, 2),
                "actual": round(b_wins / b_total, 2) if b_total else 0,
                "count": b_total,
            }
        )

    # Max drawdown (chronological order: oldest first)
    chronological = list(reversed(rows))
    max_dd = 0
    current = 0
    for r in chronological:
        if r["outcome"] == "LOSS":
            current += 1
            max_dd = max(max_dd, current)
        else:
            current = 0

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "runs": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 4),
        "calibration": calibration,
        "max_drawdown": max_dd,
    }
