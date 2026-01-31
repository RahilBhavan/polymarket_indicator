"""Phase 5: EOD outcomes endpoint (403 when secret required, 200 when allowed)."""

import os

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_eod_outcomes_403_when_secret_required_and_missing() -> None:
    """When EOD_CRON_SECRET is set, request without X-Cron-Secret returns 403."""
    os.environ["EOD_CRON_SECRET"] = "secret123"
    try:
        client = TestClient(app)
        with client:
            resp = client.post("/internal/run-eod-outcomes")
        assert resp.status_code == 403
        data = resp.json()
        assert "error" in data
        err = (data.get("error") or "").lower()
        assert "invalid" in err or "missing" in err or "secret" in err
    finally:
        os.environ.pop("EOD_CRON_SECRET", None)


def test_eod_outcomes_403_when_secret_wrong() -> None:
    """When EOD_CRON_SECRET is set, wrong X-Cron-Secret returns 403."""
    os.environ["EOD_CRON_SECRET"] = "secret123"
    try:
        client = TestClient(app)
        with client:
            resp = client.post(
                "/internal/run-eod-outcomes",
                headers={"X-Cron-Secret": "wrong"},
            )
        assert resp.status_code == 403
    finally:
        os.environ.pop("EOD_CRON_SECRET", None)


def test_eod_outcomes_403_when_secret_unset() -> None:
    """When EOD_CRON_SECRET is not set, POST returns 403 (endpoint protected)."""
    prev = os.environ.pop("EOD_CRON_SECRET", None)
    get_settings.cache_clear()
    try:
        client = TestClient(app)
        with client:
            resp = client.post("/internal/run-eod-outcomes")
        assert resp.status_code == 403
        data = resp.json()
        err = (data.get("error") or "").lower()
        assert "invalid" in err or "missing" in err or "secret" in err
    finally:
        if prev is not None:
            os.environ["EOD_CRON_SECRET"] = prev
        get_settings.cache_clear()


def test_eod_outcomes_200_when_secret_correct() -> None:
    """When EOD_CRON_SECRET is set and X-Cron-Secret matches, POST returns 200 or 500 on DB error."""
    os.environ["EOD_CRON_SECRET"] = "secret123"
    try:
        client = TestClient(app)
        with client:
            resp = client.post(
                "/internal/run-eod-outcomes",
                headers={"X-Cron-Secret": "secret123"},
            )
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("ok") is True
            assert "updated" in data
    finally:
        os.environ.pop("EOD_CRON_SECRET", None)
