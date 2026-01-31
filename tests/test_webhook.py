"""Webhook verification: 403 when secret missing or wrong."""

from fastapi.testclient import TestClient

from app.main import app
from app.telegram.webhook import HEADER_NAME


def test_webhook_returns_403_when_secret_missing() -> None:
    """POST without X-Telegram-Bot-Api-Secret-Token returns 403."""
    client = TestClient(app)
    # Need to trigger lifespan for init_pool; TestClient does that
    with client:
        resp = client.post("/webhook/telegram", json={"update_id": 1})
    assert resp.status_code == 403


def test_webhook_returns_403_when_secret_wrong() -> None:
    """POST with wrong secret returns 403."""
    import os

    os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "correct_secret")
    client = TestClient(app)
    with client:
        resp = client.post(
            "/webhook/telegram",
            json={"update_id": 1},
            headers={HEADER_NAME: "wrong_secret"},
        )
    assert resp.status_code == 403
