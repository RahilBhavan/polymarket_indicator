"""Sync signal_runs from Postgres to Google Sheets in batches."""

import os
from datetime import datetime
from typing import Any

from app.db.session import acquire
from app.logging_config import get_logger
from app.sheets.client import _get_credentials, sheets_client_available

logger = get_logger(__name__)

BATCH_SIZE = 50


async def fetch_recent_runs(limit: int = 100) -> list[dict[str, Any]]:
    """Fetch recent signal_runs with outcome for Sheets rows."""
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, run_at, market_slug, direction, model_p, market_p, edge,
                   recommended_usd, outcome, status
            FROM signal_runs
            ORDER BY run_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


def _run_to_row(r: dict[str, Any]) -> list[Any]:
    """Convert one signal_run to sheet row: Date, Timestamp, Asset, Direction, Confidence, ..."""
    run_at = r.get("run_at")
    if isinstance(run_at, datetime):
        date_str = run_at.strftime("%Y-%m-%d")
        ts_str = run_at.strftime("%Y-%m-%d %H:%M:%S")
    else:
        date_str = ts_str = str(run_at) if run_at else ""
    return [
        date_str,
        ts_str,
        "BTC",
        r.get("direction") or "",
        f"{float(r['model_p']):.0%}" if r.get("model_p") is not None else "",
        float(r["model_p"]) if r.get("model_p") is not None else "",
        float(r["market_p"]) if r.get("market_p") is not None else "",
        float(r["edge"]) if r.get("edge") is not None else "",
        float(r["recommended_usd"]) if r.get("recommended_usd") is not None else "",
        r.get("outcome") or "",
        "WIN" if r.get("outcome") == "WIN" else ("LOSS" if r.get("outcome") == "LOSS" else "SKIP"),
        r.get("status") or "",
    ]


async def sync_to_sheets() -> bool:
    """
    Append recent runs to Sheet "Daily Signals". Uses batchUpdate; respects 60 req/min.
    Returns True if sync succeeded.
    """
    if not sheets_client_available():
        logger.info("sheets_skip", reason="credentials_or_id_missing")
        return False
    creds = _get_credentials()
    sheet_id = os.environ.get("SPREADSHEET_ID")
    if not creds or not sheet_id:
        return False
    runs = await fetch_recent_runs(limit=BATCH_SIZE)
    if not runs:
        return True
    rows = [_run_to_row(r) for r in reversed(runs)]
    try:
        from googleapiclient.discovery import (
            build,
        )  # optional: pip install google-api-python-client

        service = build("sheets", "v4", credentials=creds)
        body = {"values": rows}
        # Append to "Daily Signals" (or first sheet)
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Daily Signals!A:P",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()
        logger.info("sheets_sync_ok", rows=len(rows))
        return True
    except Exception as e:
        logger.warning("sheets_sync_failed", error=str(e))
        return False
