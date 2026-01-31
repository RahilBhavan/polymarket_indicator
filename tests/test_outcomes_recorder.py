"""Phase 5: Recorder (record_run_outcome validation; fetch_unresolved_runs returns list)."""

import pytest

from app.outcomes.recorder import record_run_outcome


@pytest.mark.asyncio
async def test_record_run_outcome_invalid_outcome_raises() -> None:
    """record_run_outcome raises ValueError for invalid outcome."""
    with pytest.raises(ValueError, match="outcome must be WIN, LOSS, or SKIP"):
        await record_run_outcome(99999, "INVALID")
    with pytest.raises(ValueError, match="outcome must be WIN, LOSS, or SKIP"):
        await record_run_outcome(99999, "WINNER")


@pytest.mark.asyncio
async def test_record_run_outcome_invalid_actual_result_raises() -> None:
    """record_run_outcome raises ValueError for invalid actual_result."""
    with pytest.raises(ValueError, match="actual_result must be YES or NO"):
        await record_run_outcome(99999, "WIN", actual_result="MAYBE")
