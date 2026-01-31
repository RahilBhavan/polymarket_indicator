"""Async Postgres connection pool. No secrets in logs."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from asyncpg import Pool

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

_pool: Pool | None = None


async def init_pool() -> Pool | None:
    """Create connection pool. Call once at startup. Returns None if DB unreachable (app still runs)."""
    global _pool
    settings = get_settings()
    try:
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=1,
            max_size=5,
            command_timeout=10,
        )
        logger.info("db_pool_created", min_size=1, max_size=5)
        return _pool
    except Exception as e:
        logger.warning("db_pool_init_failed", error=str(e))
        _pool = None
        return None


async def close_pool() -> None:
    """Close pool. Call at shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("db_pool_closed")


def get_pool() -> Pool | None:
    """Return the global pool, or None if not initialized (e.g. DB down)."""
    return _pool


@asynccontextmanager
async def acquire() -> AsyncGenerator[asyncpg.Connection, None]:
    """Acquire a connection from the pool. Raises if pool not initialized."""
    pool = get_pool()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    async with pool.acquire() as conn:
        yield conn


async def health_check() -> bool:
    """Return True if DB is reachable."""
    pool = get_pool()
    if pool is None:
        return False
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception as e:
        logger.warning("db_health_check_failed", error=str(e))
        return False
