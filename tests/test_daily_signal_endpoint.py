"""Daily signal endpoint: 403 when secret missing/wrong, 200 when correct."""

import os

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_daily_signal_403_when_secret_missing() -> None:
    """When EOD_CRON_SECRET is set, request without X-Cron-Secret returns 403."""
    os.environ["EOD_CRON_SECRET"] = "cron_secret_xyz"
    try:
        get_settings.cache_clear()
        client = TestClient(app)
        with client:
            resp = client.post("/internal/run-daily-signal")
        assert resp.status_code == 403
        data = resp.json()
        assert "error" in data
    finally:
        os.environ.pop("EOD_CRON_SECRET", None)
        get_settings.cache_clear()


def test_daily_signal_403_when_secret_wrong() -> None:
    """Wrong X-Cron-Secret returns 403."""
    os.environ["EOD_CRON_SECRET"] = "cron_secret_xyz"
    try:
        get_settings.cache_clear()
        client = TestClient(app)
        with client:
            resp = client.post(
                "/internal/run-daily-signal",
                headers={"X-Cron-Secret": "wrong"},
            )
        assert resp.status_code == 403
    finally:
        os.environ.pop("EOD_CRON_SECRET", None)
        get_settings.cache_clear()


def test_daily_signal_200_when_secret_correct() -> None:
    """When X-Cron-Secret matches, POST returns 200 with ok, signal_sent, reason, recipients."""
    os.environ["EOD_CRON_SECRET"] = "cron_secret_xyz"
    try:
        get_settings.cache_clear()
        client = TestClient(app)
        with client:
            resp = client.post(
                "/internal/run-daily-signal",
                headers={"X-Cron-Secret": "cron_secret_xyz"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert "signal_sent" in data
        assert "reason" in data
        assert "recipients" in data
    finally:
        os.environ.pop("EOD_CRON_SECRET", None)
        get_settings.cache_clear()
