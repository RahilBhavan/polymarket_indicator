"""Drawdown from sequence of WIN/LOSS (simplified: no PnL, just run of losses)."""

from app.db.signal_runs import fetch_resolved_outcomes


async def max_drawdown(limit: int = 100) -> int:
    """
    Max consecutive losses in last N resolved runs.
    """
    rows = await fetch_resolved_outcomes(limit=limit)
    if not rows:
        return 0
    # Reverse so chronological order
    outcomes = [r["outcome"] for r in reversed(rows)]
    max_dd = 0
    current = 0
    for o in outcomes:
        if o == "LOSS":
            current += 1
            max_dd = max(max_dd, current)
        else:
            current = 0
    return max_dd
