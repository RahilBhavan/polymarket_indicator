"""Upsert market metadata (condition_id, slug, resolution_source, end_date_utc) for outcome recording."""

from datetime import datetime

from app.db.session import acquire, get_pool
from app.logging_config import get_logger

logger = get_logger(__name__)


def _parse_end_date_utc(end_date: str | None) -> datetime | None:
    """Parse Gamma end_date (ISO) to datetime for DB."""
    if not end_date:
        return None
    try:
        s = end_date.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


async def upsert_market_metadata(
    condition_id: str,
    slug: str | None = None,
    resolution_source: str | None = None,
    end_date: str | None = None,
) -> None:
    """
    Upsert market_metadata row. Call when we select a market (e.g. /signal stub).
    end_date: ISO string from Gamma (e.g. 2026-01-30T23:59:59Z).
    """
    pool = get_pool()
    if pool is None:
        logger.debug("market_metadata_skip_no_pool", condition_id=condition_id)
        return
    end_dt = _parse_end_date_utc(end_date)
    try:
        async with acquire() as conn:
            await conn.execute(
                """
                INSERT INTO market_metadata (condition_id, slug, resolution_source, end_date_utc, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (condition_id) DO UPDATE SET
                    slug = EXCLUDED.slug,
                    resolution_source = EXCLUDED.resolution_source,
                    end_date_utc = EXCLUDED.end_date_utc,
                    updated_at = NOW()
                """,
                condition_id,
                slug,
                resolution_source,
                end_dt,
            )
        logger.debug("market_metadata_upserted", condition_id=condition_id, slug=slug)
    except Exception as e:
        logger.warning("market_metadata_upsert_failed", condition_id=condition_id, error=str(e))
