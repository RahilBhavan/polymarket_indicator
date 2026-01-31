"""Rolling win rate, streak, profit factor."""

from app.db.signal_runs import fetch_resolved_outcomes
from app.logging_config import get_logger

logger = get_logger(__name__)


async def rolling_win_rate(limit: int = 30) -> dict[str, float | int]:
    """Win rate and count over last N resolved runs (WIN/LOSS only, exclude SKIP)."""
    rows = await fetch_resolved_outcomes(limit=limit)
    if not rows:
        return {"win_rate": 0.0, "wins": 0, "losses": 0, "total": 0, "profit_factor": None}
    wins = sum(1 for r in rows if r["outcome"] == "WIN")
    total = len(rows)
    # Profit factor = gross profit / gross loss when we have PnL; not stored yet
    return {
        "win_rate": round(wins / total, 4) if total else 0.0,
        "wins": wins,
        "losses": total - wins,
        "total": total,
        "profit_factor": None,
    }


async def current_streak() -> int:
    """Current streak: consecutive WINs (positive) or LOSSes (negative)."""
    rows = await fetch_resolved_outcomes(limit=100)
    if not rows:
        return 0
    first = rows[0]["outcome"]
    streak = 0
    for r in rows:
        if r["outcome"] != first:
            break
        streak += 1 if first == "WIN" else -1
    return streak
