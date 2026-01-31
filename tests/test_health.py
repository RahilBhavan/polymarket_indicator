"""Health endpoint: 200 when DB up (or 503 when down); includes last_signal_at and data_sources when 200."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_200_or_503() -> None:
    """GET /health returns 200 with db connected or 503 if DB unavailable."""
    client = TestClient(app)
    with client:
        resp = client.get("/health")
    # If test DB is not running, we get 503; if running, 200
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "status" in data
    if resp.status_code == 200:
        assert data.get("db") == "connected"
        assert "last_signal_at" in data
        assert "data_sources" in data
        assert isinstance(data["data_sources"], list)
    else:
        assert data.get("db") == "disconnected"
