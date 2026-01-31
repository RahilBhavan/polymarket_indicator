"""Base fetcher: retry with exponential backoff, circuit breaker."""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class FetcherResult:
    """Single source result: raw value, normalized score (-2..+2 or 0-1), stale flag."""

    source_id: str
    raw_value: str | None
    normalized_score: float | None
    stale: bool = False
    error: str | None = None


@dataclass
class CircuitState:
    """Circuit breaker state per source."""

    failure_count: int = 0
    open_until: float = 0.0


_circuits: dict[str, CircuitState] = {}


def reset_circuits() -> None:
    """Reset all circuit states. Use in tests only."""
    _circuits.clear()


def _circuit_open(source_id: str) -> bool:
    now = time.monotonic()
    state = _circuits.get(source_id)
    if not state:
        return False
    if state.open_until > now:
        return True
    state.failure_count = 0
    state.open_until = 0.0
    return False


def _record_success(source_id: str) -> None:
    state = _circuits.get(source_id)
    if state:
        state.failure_count = 0


def _record_failure(source_id: str) -> None:
    settings = get_settings()
    state = _circuits.setdefault(source_id, CircuitState())
    state.failure_count += 1
    if state.failure_count >= settings.circuit_failure_threshold:
        state.open_until = time.monotonic() + settings.circuit_open_seconds
        logger.warning(
            "circuit_open",
            source_id=source_id,
            open_seconds=settings.circuit_open_seconds,
        )


async def with_retry(
    source_id: str,
    fetch_fn: Any,
    *args: Any,
    **kwargs: Any,
) -> FetcherResult:
    """Run fetch_fn with retries; return FetcherResult with error on failure."""
    if _circuit_open(source_id):
        return FetcherResult(
            source_id=source_id,
            raw_value=None,
            normalized_score=None,
            stale=False,
            error="circuit_open",
        )
    settings = get_settings()
    last_error: Exception | None = None
    for attempt in range(settings.retry_attempts):
        try:
            result = await fetch_fn(*args, **kwargs)
            _record_success(source_id)
            return result
        except Exception as e:
            last_error = e
            delay = settings.retry_base_delay * (2**attempt)
            logger.warning(
                "fetcher_retry",
                source_id=source_id,
                attempt=attempt + 1,
                error=str(e),
                delay=delay,
            )
            await asyncio.sleep(delay)
    _record_failure(source_id)
    return FetcherResult(
        source_id=source_id,
        raw_value=None,
        normalized_score=None,
        stale=False,
        error=str(last_error) if last_error else "unknown",
    )


def get_fetcher_timeout() -> float:
    """HTTP timeout for fetcher requests (seconds)."""
    return get_settings().fetcher_timeout


def error_result(source_id: str, error: str | Exception) -> FetcherResult:
    """Build a failed FetcherResult for the given source. Logs warning."""
    err_str = str(error) if isinstance(error, Exception) else error
    logger.warning("fetcher_failed", source_id=source_id, error=err_str)
    return FetcherResult(
        source_id=source_id,
        raw_value=None,
        normalized_score=None,
        stale=False,
        error=err_str,
    )


class BaseFetcher(ABC):
    """Abstract fetcher: fetch() returns FetcherResult. Normalize in subclass."""

    source_id: str = "base"
    max_age_seconds: float = 86400  # 24h default

    def _error_result(self, error: str | Exception) -> FetcherResult:
        """Return a failed FetcherResult for this source. Use in except blocks."""
        return error_result(self.source_id, error)

    @abstractmethod
    async def fetch(self) -> FetcherResult:
        """Fetch and return result. Use with_retry inside if needed."""
        ...

    def normalize(self, raw: str | float | None) -> float | None:
        """Map raw value to normalized score (-2 to +2). Override in subclass."""
        return None
