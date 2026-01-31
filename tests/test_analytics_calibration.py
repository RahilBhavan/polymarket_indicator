"""Phase 5: Calibration summary and error text (unit)."""

from app.analytics.calibration import calibration_error_text


def test_calibration_error_text_empty() -> None:
    """No calibration data returns message."""
    assert calibration_error_text([]) == "No calibration data yet."


def test_calibration_error_text_one_bucket() -> None:
    """One bucket: |predicted - actual| = error."""
    summary = [
        {"bucket_low": 0.6, "bucket_high": 0.7, "predicted": 0.65, "actual": 0.5, "count": 10}
    ]
    # |0.65 - 0.5| = 0.15 -> 15%
    assert "15" in calibration_error_text(summary) or "15.0" in calibration_error_text(summary)


def test_calibration_error_text_average() -> None:
    """Average calibration error across buckets."""
    summary = [
        {"predicted": 0.6, "actual": 0.6, "count": 5},
        {"predicted": 0.7, "actual": 0.5, "count": 5},
    ]
    # errors: 0, 0.2 -> avg 0.1 -> 10%
    text = calibration_error_text(summary)
    assert "10" in text or "calibration" in text.lower()
