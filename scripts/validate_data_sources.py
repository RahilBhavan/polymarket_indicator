#!/usr/bin/env -S uv run python
"""
Validate data sources: run all fetchers, print per-source status and raw values.
Exits non-zero if more than max_failures sources failed or a critical source is missing.
Usage: uv run python scripts/validate_data_sources.py [--max-failures N] [--critical price_ma,etf_flows]
"""

import argparse
import asyncio
import sys

# Add src to path so app is importable
sys.path.insert(0, __file__.rsplit("/", 1)[0].replace("\\", "/") + "/../src")

from app.fetchers.registry import run_all_fetchers


# Sources that must have data (no error) for validation to pass
DEFAULT_CRITICAL_SOURCES = ("price_ma", "etf_flows")


async def run_validation(
    max_failures: int = 3,
    critical_sources: tuple[str, ...] = DEFAULT_CRITICAL_SOURCES,
) -> int:
    """
    Run all fetchers; print status and raw values; return 0 if ok, 1 if too many failures
    or a critical source is missing.
    """
    snapshot = await run_all_fetchers()
    failed = 0
    critical_missing: list[str] = []
    for r in snapshot.results:
        status = "fail" if r.error else ("stale" if r.stale else "ok")
        raw = r.raw_value if r.raw_value is not None else "(none)"
        err = f" error={r.error}" if r.error else ""
        print(f"{r.source_id}: {status} raw={raw}{err}")
        if r.error:
            failed += 1
            if r.source_id in critical_sources:
                critical_missing.append(r.source_id)
    if failed > max_failures:
        print(
            f"Validation failed: {failed} sources failed (max allowed: {max_failures})",
            file=sys.stderr,
        )
        return 1
    if critical_missing:
        print(
            f"Validation failed: critical sources missing or failed: {critical_missing}",
            file=sys.stderr,
        )
        return 1
    print("Validation passed: all critical sources ok.", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate data sources (run fetchers, check status)")
    parser.add_argument(
        "--max-failures",
        type=int,
        default=3,
        help="Max number of sources allowed to fail (default: 3)",
    )
    parser.add_argument(
        "--critical",
        type=str,
        default=",".join(DEFAULT_CRITICAL_SOURCES),
        help="Comma-separated source_ids that must succeed (default: price_ma,etf_flows)",
    )
    args = parser.parse_args()
    critical_sources = tuple(s.strip() for s in args.critical.split(",") if s.strip())
    return asyncio.run(run_validation(args.max_failures, critical_sources))


if __name__ == "__main__":
    sys.exit(main())
