"""Config loads from env and validates."""

import os

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


def test_allowed_user_ids_list() -> None:
    """Parse comma-separated user IDs to list of ints."""
    os.environ["TELEGRAM_ALLOWED_USER_IDS"] = "111, 222, 333"
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert s.allowed_user_ids_list() == [111, 222, 333]
    finally:
        get_settings.cache_clear()


def test_fetcher_config_defaults() -> None:
    """Fetcher-related config has expected defaults (Phase 3)."""
    s = get_settings()
    assert s.fetcher_timeout > 0
    assert s.circuit_failure_threshold >= 1
    assert s.circuit_open_seconds > 0
    assert s.cache_ttl_seconds > 0
    assert s.retry_attempts >= 1
    assert s.retry_base_delay > 0


def test_settings_invalid_allowed_user_ids_raises() -> None:
    """Invalid TELEGRAM_ALLOWED_USER_IDS (e.g. non-integer) raises ValidationError at startup."""
    get_settings.cache_clear()
    orig = os.environ.get("TELEGRAM_ALLOWED_USER_IDS")
    try:
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = "111,not_a_number,333"
        with pytest.raises(ValidationError):
            Settings()
    finally:
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = orig or "12345"
        get_settings.cache_clear()


def test_settings_requires_required_vars() -> None:
    """Missing required env raises ValidationError."""
    get_settings.cache_clear()
    try:
        orig = os.environ.get("TELEGRAM_BOT_TOKEN")
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        try:
            with pytest.raises(ValidationError):
                Settings()
        finally:
            if orig is not None:
                os.environ["TELEGRAM_BOT_TOKEN"] = orig
    finally:
        get_settings.cache_clear()
