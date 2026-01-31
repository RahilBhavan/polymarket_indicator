"""Factor attribution: avg contribution on WIN vs LOSS (optional)."""

from app.db.session import acquire


async def factor_attribution(limit: int = 50) -> list[dict]:
    """
    For each factor (from reasoning_json), average contribution on WIN vs LOSS.
    Returns list of {factor, avg_win, avg_loss, count_win, count_loss}.
    """
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT outcome, reasoning_json FROM signal_runs
            WHERE outcome IN ('WIN', 'LOSS') AND reasoning_json IS NOT NULL
            ORDER BY run_at DESC
            LIMIT $1
            """,
            limit,
        )
    if not rows:
        return []
    wins: dict[str, list[float]] = {}
    losses: dict[str, list[float]] = {}
    for r in rows:
        outcome = r["outcome"]
        reasoning = r["reasoning_json"] or []
        for item in reasoning:
            factor = item.get("factor")
            contrib = item.get("contribution")
            if factor is None or contrib is None:
                continue
            if outcome == "WIN":
                wins.setdefault(factor, []).append(contrib)
            else:
                losses.setdefault(factor, []).append(contrib)
    out = []
    all_factors = set(wins) | set(losses)
    for factor in sorted(all_factors):
        w_list = wins.get(factor, [])
        l_list = losses.get(factor, [])
        out.append(
            {
                "factor": factor,
                "avg_win": round(sum(w_list) / len(w_list), 4) if w_list else None,
                "avg_loss": round(sum(l_list) / len(l_list), 4) if l_list else None,
                "count_win": len(w_list),
                "count_loss": len(l_list),
            }
        )
    return out
