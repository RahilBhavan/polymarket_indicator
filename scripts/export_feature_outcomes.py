#!/usr/bin/env -S uv run python
"""
Export resolved signal runs with their feature snapshots to CSV for analysis.
Usage: uv run python scripts/export_feature_outcomes.py [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--out file.csv]
"""

import argparse
import asyncio
import csv
import sys
from datetime import date, timedelta

# Add src to path so app is importable
sys.path.insert(0, __file__.rsplit("/", 1)[0].replace("\\", "/") + "/../src")

from app.db.feature_snapshots import fetch_resolved_runs_with_features
from app.db.session import init_pool


def parse_date(s: str) -> date:
    """Parse YYYY-MM-DD to date."""
    return date.fromisoformat(s)


async def run_export(
    date_from: date,
    date_to: date,
    limit: int,
    out_path: str | None,
) -> None:
    """Fetch feature+outcome rows and write CSV to stdout or file."""
    await init_pool()
    rows = await fetch_resolved_runs_with_features(date_from, date_to, limit=limit)
    if not rows:
        print("No resolved runs with features in date range.", file=sys.stderr)
        return
    fieldnames = [
        "signal_run_id",
        "run_at",
        "outcome",
        "actual_result",
        "model_p",
        "source_id",
        "raw_value",
        "normalized_score",
        "stale",
    ]
    out = open(out_path, "w", newline="") if out_path else sys.stdout
    writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        row = dict(r)
        if row.get("run_at") is not None and hasattr(row["run_at"], "isoformat"):
            row["run_at"] = row["run_at"].isoformat()
        if row.get("model_p") is not None:
            row["model_p"] = float(row["model_p"])
        writer.writerow(row)
    if out_path:
        out.close()
    else:
        print(f"Exported {len(rows)} rows to stdout.", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export feature+outcome history to CSV")
    parser.add_argument(
        "--from",
        dest="date_from",
        type=str,
        default=(date.today() - timedelta(days=90)).isoformat(),
        help="Start date YYYY-MM-DD (default: 90 days ago)",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        type=str,
        default=date.today().isoformat(),
        help="End date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output CSV file (default: stdout)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Max rows (default: 5000)",
    )
    args = parser.parse_args()
    date_from = parse_date(args.date_from)
    date_to = parse_date(args.date_to)
    asyncio.run(run_export(date_from, date_to, args.limit, args.out))


if __name__ == "__main__":
    main()
