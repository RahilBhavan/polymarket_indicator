"""Pytest fixtures. Use asyncio for async tests."""

import os
from typing import Generator

import pytest


@pytest.fixture(scope="session", autouse=True)
def _minimal_env() -> Generator[None, None, None]:
    """Set minimal env for all tests so get_settings() and validate_env() at app startup succeed."""
    # Must satisfy scripts/validate_env.py: token format + min length, secret >= 32 chars, user ID >= 5 digits.
    # Use assignment (not setdefault) so CI's short placeholder values are overridden.
    _token = "1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    _secret = "a" * 32
    _db = "postgresql://postgres:postgres@localhost:5432/cryptosignal_test"
    os.environ["TELEGRAM_BOT_TOKEN"] = _token
    os.environ["TELEGRAM_WEBHOOK_SECRET"] = _secret
    os.environ["TELEGRAM_ALLOWED_USER_IDS"] = "12345"
    os.environ["DATABASE_URL"] = _db
    os.environ["CRYPTOSIGNAL_SKIP_STARTUP_VALIDATION"] = "1"
    yield
