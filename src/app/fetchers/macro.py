"""Macro calendar: FOMC/CPI within 48h. FMP economic calendar when FMP_API_KEY set; else no_event."""

import os
from datetime import datetime, timezone

import httpx
from app.fetchers.base import BaseFetcher, FetcherResult, get_fetcher_timeout, with_retry

# FMP economic calendar (free tier: 250 req/day). Requires apikey query param.
DEFAULT_FMP_ECONOMIC_CALENDAR_URL = "https://financialmodelingprep.com/stable/economic-calendar"
# Event name substrings we treat as high-impact (FOMC, CPI)
MACRO_KEYWORDS = ("fomc", "fed rate", "cpi ", " consumer price ", "consumer price index")
# Hours ahead to consider "within 48h"
HOURS_AHEAD = 48


def _event_in_next_48h(events: list, now_utc: datetime) -> bool:
    """Return True if any event has a keyword and date is within next 48h."""
    cutoff = now_utc.timestamp() + HOURS_AHEAD * 3600
    for item in events:
        if not isinstance(item, dict):
            continue
        name = (item.get("event") or item.get("title") or item.get("name") or "").lower()
        if not any(kw in name for kw in MACRO_KEYWORDS):
            continue
        # Parse date: may be "date", "releaseDate", "timestamp", or ISO string
        raw = item.get("date") or item.get("releaseDate") or item.get("timestamp")
        if raw is None:
            continue
        try:
            if isinstance(raw, (int, float)):
                ts = float(raw)
                if ts > 1e10:
                    ts = ts / 1000.0  # ms to seconds
            else:
                s = str(raw).replace("Z", "+00:00").strip()
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                ts = dt.timestamp()
            if 0 < ts <= cutoff:
                return True
        except (TypeError, ValueError):
            continue
    return False


class MacroFetcher(BaseFetcher):
    source_id = "macro"
    max_age_seconds = 86400

    def normalize(self, raw: str | float | None) -> float | None:
        """No events: +0.5, FOMC/CPI within 48h: -1."""
        if raw is None:
            return None
        try:
            v = float(raw)
            return v
        except (TypeError, ValueError):
            return None

    async def _do_fetch(self) -> FetcherResult:
        api_key = (os.getenv("FMP_API_KEY") or "").strip()
        url_base = (os.getenv("FMP_ECONOMIC_CALENDAR_URL") or DEFAULT_FMP_ECONOMIC_CALENDAR_URL).strip()
        if not api_key:
            return FetcherResult(
                source_id=self.source_id,
                raw_value="no_event",
                normalized_score=0.5,
                stale=False,
            )
        url = f"{url_base}?apikey={api_key}"
        try:
            async with httpx.AsyncClient(timeout=get_fetcher_timeout()) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            if not isinstance(data, list):
                data = data if isinstance(data, list) else (data.get("data") or data.get("events") or [])
            if not isinstance(data, list):
                data = []
            now_utc = datetime.now(timezone.utc)
            has_event_48h = _event_in_next_48h(data, now_utc)
            raw_value = "fomc_cpi_48h" if has_event_48h else "no_event"
            score = -1.0 if has_event_48h else 0.5
            return FetcherResult(
                source_id=self.source_id,
                raw_value=raw_value,
                normalized_score=score,
                stale=False,
            )
        except Exception as e:
            return FetcherResult(
                source_id=self.source_id,
                raw_value="no_event",
                normalized_score=0.5,
                stale=False,
                error=str(e),
            )

    async def fetch(self) -> FetcherResult:
        return await with_retry(self.source_id, self._do_fetch)
