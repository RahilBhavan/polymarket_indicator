#!/usr/bin/env -S uv run python
"""
Slippage report: load last N paper runs with order_book_snapshot, compute VWAP vs quoted price.
Output: count, avg slippage (bps), 95th percentile (bps).
Usage: uv run python scripts/slippage_report.py [--limit N] [--database-url URL]
"""

import argparse
import asyncio
import os
import sys
from typing import Any

# Add src to path so app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.analytics.slippage_audit import slippage_bps, vwap_for_size_usd
from app.db.session import acquire, init_pool
from app.polymarket.models import OrderBook, OrderBookLevel


def snapshot_to_order_book(snapshot: dict[str, Any]) -> OrderBook:
    """Build OrderBook from stored JSON snapshot (bids/asks list of {price, size})."""
    bids = [
        OrderBookLevel(price=float(x["price"]), size=float(x["size"]))
        for x in snapshot.get("bids") or []
    ]
    asks = [
        OrderBookLevel(price=float(x["price"]), size=float(x["size"]))
        for x in snapshot.get("asks") or []
    ]
    return OrderBook(bids=bids, asks=asks)


async def run_slippage_report(limit: int = 20) -> None:
    """Load last N runs with order_book_snapshot; compute and print slippage stats."""
    await init_pool()
    bps_list: list[float] = []
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, order_book_snapshot, recommended_usd, market_p
            FROM signal_runs
            WHERE order_book_snapshot IS NOT NULL
              AND recommended_usd IS NOT NULL AND recommended_usd > 0
              AND market_p IS NOT NULL AND market_p > 0
            ORDER BY run_at DESC
            LIMIT $1
            """,
            limit,
        )
    for r in rows:
        snap = r["order_book_snapshot"]
        if not snap or not isinstance(snap, dict):
            continue
        book = snapshot_to_order_book(snap)
        rec_usd = float(r["recommended_usd"])
        quoted = float(r["market_p"])
        vwap = vwap_for_size_usd(book, "ask", rec_usd)
        if vwap is None:
            continue
        bps = slippage_bps(quoted, vwap)
        bps_list.append(bps)
    if not bps_list:
        print("No paper runs with order_book_snapshot and valid recommended_usd/market_p.")
        return
    bps_list.sort()
    avg_bps = sum(bps_list) / len(bps_list)
    p95_idx = max(0, int(len(bps_list) * 0.95) - 1)
    p95_bps = bps_list[p95_idx]
    print(f"Runs: {len(bps_list)}")
    print(f"Avg slippage: {avg_bps:.1f} bps")
    print(f"95th percentile: {p95_bps:.1f} bps")


def main() -> None:
    parser = argparse.ArgumentParser(description="Slippage report for paper runs")
    parser.add_argument("--limit", type=int, default=20, help="Max runs to include")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres URL (default: DATABASE_URL)",
    )
    args = parser.parse_args()
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    asyncio.run(run_slippage_report(limit=args.limit))


if __name__ == "__main__":
    main()
