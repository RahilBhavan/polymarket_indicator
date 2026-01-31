"""EOD job: record outcome (WIN/LOSS/SKIP) for resolved signal runs."""

from datetime import datetime, timezone

from app.db.session import acquire
from app.logging_config import get_logger
from app.outcomes.resolution import resolve_market_outcome
from app.polymarket.client import fetch_markets, parse_market

logger = get_logger(__name__)


async def record_run_outcome(
    signal_run_id: int,
    outcome: str,
    actual_result: str | None = None,
) -> None:
    """
    Set outcome (WIN | LOSS | SKIP), optional actual_result (YES | NO), and resolved_at.
    Only updates when outcome IS NULL (idempotent; do not overwrite existing outcome).
    """
    if outcome not in ("WIN", "LOSS", "SKIP"):
        raise ValueError("outcome must be WIN, LOSS, or SKIP")
    if actual_result is not None and actual_result not in ("YES", "NO"):
        raise ValueError("actual_result must be YES or NO")
    now = datetime.now(timezone.utc)
    async with acquire() as conn:
        await conn.execute(
            """
            UPDATE signal_runs
            SET outcome = $1, resolved_at = $2, actual_result = $3
            WHERE id = $4 AND outcome IS NULL
            """,
            outcome,
            now,
            actual_result,
            signal_run_id,
        )
    logger.info(
        "outcome_recorded",
        signal_run_id=signal_run_id,
        outcome=outcome,
        actual_result=actual_result,
    )


async def fetch_unresolved_runs() -> list[dict]:
    """
    Return signal_runs that have no outcome, market has ended (end_date_utc < now),
    and direction is YES or NO (exclude NO_TRADE). Joins with market_metadata for
    resolution_source and end_date_utc. Skips runs with NULL market_condition_id.
    """
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sr.id, sr.run_at, sr.market_slug, sr.market_condition_id, sr.direction,
                   mm.resolution_source, mm.end_date_utc, mm.slug AS meta_slug
            FROM signal_runs sr
            JOIN market_metadata mm ON mm.condition_id = sr.market_condition_id
            WHERE sr.outcome IS NULL
              AND sr.market_condition_id IS NOT NULL
              AND sr.status = 'ok'
              AND sr.direction IN ('YES', 'NO')
              AND mm.end_date_utc IS NOT NULL
              AND mm.end_date_utc < NOW()
            ORDER BY sr.run_at ASC
            """,
        )
    return [dict(r) for r in rows]


async def _get_question_and_outcomes_for_slug(slug: str | None) -> tuple[str | None, list[str]]:
    """Fetch market from Gamma by slug (closed); return (question, outcomes_list) for resolution."""
    if not slug:
        return (None, [])
    try:
        data = await fetch_markets(closed=True, slug=slug, limit=1)
        if not data or not isinstance(data, list):
            return (slug, [])
        raw = data[0]
        market = parse_market(raw)
        if not market:
            return (slug, [])
        question = market.question or slug
        outcomes = market.outcomes_list
        return (question, outcomes)
    except Exception as e:
        logger.warning("fetch_question_failed", slug=slug, error=str(e))
        return (slug, [])


async def run_eod_outcomes() -> dict:
    """
    EOD job: for each unresolved run whose market has ended, resolve outcome
    (fetch close from resolution source, compare to rule), set WIN/LOSS and actual_result.
    Does not overwrite existing outcomes (idempotent). Returns {"updated": int, "failed": list}.
    Per-run failures are logged and appended to failed; loop continues.
    """
    runs = await fetch_unresolved_runs()
    updated = 0
    failed: list[dict] = []
    for run in runs:
        run_id = run["id"]
        direction = run["direction"]
        resolution_source = run.get("resolution_source")
        end_date_utc = run.get("end_date_utc")
        market_slug = run.get("market_slug")

        try:
            slug_or_question = market_slug
            question, outcomes = await _get_question_and_outcomes_for_slug(market_slug)
            if question:
                slug_or_question = question

            actual_result = await resolve_market_outcome(
                resolution_source,
                end_date_utc,
                slug_or_question,
                outcomes=outcomes,
            )
            if actual_result is None:
                logger.info(
                    "eod_skip_unresolved",
                    signal_run_id=run_id,
                    reason="resolution_failed_or_unsupported",
                )
                continue

            # WIN if prediction matched outcome; LOSS otherwise
            if direction == "YES" and actual_result == "YES":
                outcome = "WIN"
            elif direction == "NO" and actual_result == "NO":
                outcome = "WIN"
            else:
                outcome = "LOSS"

            await record_run_outcome(run_id, outcome, actual_result=actual_result)
            updated += 1
        except Exception as e:
            logger.warning("eod_run_failed", signal_run_id=run_id, error=str(e))
            failed.append({"run_id": run_id, "error": str(e)})
    return {"updated": updated, "failed": failed}
