"""User prefs: get_weights with optional fetchers; user_prefs defaults."""

import os


from app.config import get_settings
from app.signal.weights import DEFAULT_WEIGHTS, get_weights


def test_get_weights_returns_defaults_without_env_overrides() -> None:
    """get_weights returns default weights when no weight env vars are set."""
    # Clear any weight env vars so we get defaults
    for key in list(os.environ):
        if key.startswith("WEIGHT_") or key.startswith("FETCH_"):
            os.environ.pop(key, None)
    get_settings.cache_clear()
    try:
        w = get_weights()
        assert set(w.keys()) >= set(DEFAULT_WEIGHTS.keys())
        for k, v in DEFAULT_WEIGHTS.items():
            assert w.get(k) == v
    finally:
        get_settings.cache_clear()


def test_get_weights_includes_optional_fetchers_when_enabled() -> None:
    """When FETCH_COINBASE_PREMIUM=true, get_weights includes coinbase_premium."""
    os.environ["FETCH_COINBASE_PREMIUM"] = "true"
    get_settings.cache_clear()
    try:
        w = get_weights()
        assert "coinbase_premium" in w
        assert w["coinbase_premium"] > 0
    finally:
        os.environ.pop("FETCH_COINBASE_PREMIUM", None)
        get_settings.cache_clear()
