"""Pytest fixtures. Use asyncio for async tests."""

import os
from typing import Generator

import pytest


@pytest.fixture(scope="session", autouse=True)
def _minimal_env() -> Generator[None, None, None]:
    """Set minimal env for all tests so get_settings() and app startup succeed."""
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
    os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test_secret")
    os.environ.setdefault("TELEGRAM_ALLOWED_USER_IDS", "12345")
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/cryptosignal_test",
    )
    yield
