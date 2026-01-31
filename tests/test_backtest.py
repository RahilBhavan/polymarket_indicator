"""Backtest: backtest_date_range returns structure and handles empty range."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.analytics.backtest import backtest_date_range


@pytest.mark.asyncio
async def test_backtest_date_range_empty_returns_zeros() -> None:
    """When no runs in range, backtest returns runs=0, wins=0, win_rate=0, max_drawdown=0."""
    start = date.today() - timedelta(days=365)
    end = start + timedelta(days=7)
    with patch("app.analytics.backtest.fetch_resolved_outcomes", new_callable=AsyncMock) as m:
        m.return_value = []
        result = await backtest_date_range(start, end)
    assert result["runs"] == 0
    assert result["wins"] == 0
    assert result["losses"] == 0
    assert result["win_rate"] == 0.0
    assert result["max_drawdown"] == 0
    assert result["date_from"] == start.isoformat()
    assert result["date_to"] == end.isoformat()
    assert result["calibration"] == []
