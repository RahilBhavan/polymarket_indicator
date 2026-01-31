"""Calibration: predicted vs actual win rate by confidence bucket."""

from app.db.signal_runs import fetch_resolved_outcomes


async def calibration_summary(bucket_size: float = 0.1) -> list[dict]:
    """
    Bucket by model_p (e.g. 0.6-0.7), compute actual win rate in bucket.
    Return list of {bucket_low, bucket_high, predicted, actual, count}.
    """
    rows = await fetch_resolved_outcomes(
        columns="model_p, outcome",
        extra_and="model_p IS NOT NULL",
    )
    if not rows:
        return []
    buckets: dict[tuple[float, float], list[str]] = {}
    for r in rows:
        p = float(r["model_p"])
        low = int(p / bucket_size) * bucket_size
        high = low + bucket_size
        key = (low, high)
        buckets.setdefault(key, []).append(r["outcome"])
    out = []
    for (low, high), outcomes in sorted(buckets.items()):
        wins = sum(1 for o in outcomes if o == "WIN")
        total = len(outcomes)
        actual = wins / total if total else 0
        predicted = (low + high) / 2
        out.append(
            {
                "bucket_low": low,
                "bucket_high": high,
                "predicted": round(predicted, 2),
                "actual": round(actual, 2),
                "count": total,
            }
        )
    return out


def calibration_error_text(summary: list[dict]) -> str:
    """One-line calibration summary for /stats (|predicted - actual| per bucket, averaged)."""
    if not summary:
        return "No calibration data yet."
    errs = [abs(s["predicted"] - s["actual"]) for s in summary]
    avg_err = sum(errs) / len(errs) if errs else 0
    return f"Avg calibration error: {avg_err:.1%}"
