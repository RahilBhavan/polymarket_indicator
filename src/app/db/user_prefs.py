"""Users and user_prefs: ensure user exists, get/set bankroll and verbosity."""

from typing import Any

from app.db.session import acquire
from app.logging_config import get_logger

logger = get_logger(__name__)


async def ensure_user(telegram_user_id: int) -> int:
    """
    Upsert user by telegram_user_id; return users.id.
    Call when a whitelisted user first uses any command so user_prefs can be used.
    """
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (telegram_user_id)
            VALUES ($1)
            ON CONFLICT (telegram_user_id) DO UPDATE SET telegram_user_id = EXCLUDED.telegram_user_id
            RETURNING id
            """,
            telegram_user_id,
        )
    return int(row["id"])


async def get_user_prefs(telegram_user_id: int) -> dict[str, Any] | None:
    """
    Return user_prefs for the user (bankroll_usd, verbose, min_confidence_pct, bet_size_usd, kelly_fraction_override).
    Returns None if user has no prefs row (use defaults).
    """
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT up.bankroll_usd, up.is_verbose, up.min_confidence_pct,
                   up.bet_size_usd, up.kelly_fraction_override
            FROM user_prefs up
            JOIN users u ON u.id = up.user_id
            WHERE u.telegram_user_id = $1
            """,
            telegram_user_id,
        )
    if row is None:
        return None
    out: dict[str, Any] = {
        "bankroll_usd": float(row["bankroll_usd"]),
        "verbose": bool(row["is_verbose"]),
        "min_confidence_pct": float(row["min_confidence_pct"]),
    }
    if row.get("bet_size_usd") is not None:
        out["bet_size_usd"] = float(row["bet_size_usd"])
    if row.get("kelly_fraction_override") is not None:
        out["kelly_fraction_override"] = float(row["kelly_fraction_override"])
    return out


async def set_user_prefs(
    telegram_user_id: int,
    *,
    bankroll_usd: float | None = None,
    verbose: bool | None = None,
    min_confidence_pct: float | None = None,
    bet_size_usd: float | None = None,
    kelly_fraction_override: float | None = None,
    clear_bet_size_usd: bool = False,
    clear_kelly_fraction_override: bool = False,
) -> None:
    """
    Update user_prefs for the user. User must exist (call ensure_user first).
    Only provided fields are updated. bet_size_usd caps Kelly recommendation; kelly_fraction_override overrides config.
    Set clear_bet_size_usd or clear_kelly_fraction_override to True to set that column to NULL.
    """
    user_id = await ensure_user(telegram_user_id)
    updates: list[str] = ["updated_at = NOW()"]
    args: list[Any] = [user_id]
    n = 2
    if bankroll_usd is not None:
        updates.append(f"bankroll_usd = ${n}")
        args.append(bankroll_usd)
        n += 1
    if verbose is not None:
        updates.append(f"is_verbose = ${n}")
        args.append(verbose)
        n += 1
    if min_confidence_pct is not None:
        updates.append(f"min_confidence_pct = ${n}")
        args.append(min_confidence_pct)
        n += 1
    if bet_size_usd is not None:
        updates.append(f"bet_size_usd = ${n}")
        args.append(bet_size_usd)
        n += 1
    elif clear_bet_size_usd:
        updates.append("bet_size_usd = NULL")
    if kelly_fraction_override is not None:
        updates.append(f"kelly_fraction_override = ${n}")
        args.append(kelly_fraction_override)
        n += 1
    elif clear_kelly_fraction_override:
        updates.append("kelly_fraction_override = NULL")
    if len(updates) <= 1:
        return
    async with acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO user_prefs (user_id, bankroll_usd, is_verbose, min_confidence_pct, updated_at)
            VALUES ($1, 1000, FALSE, 55, NOW())
            ON CONFLICT (user_id) DO UPDATE SET {", ".join(updates)}
            """,
            *args,
        )
    logger.info(
        "user_prefs_updated",
        telegram_user_id=telegram_user_id,
        bankroll_usd=bankroll_usd,
        verbose=verbose,
        min_confidence_pct=min_confidence_pct,
        bet_size_usd=bet_size_usd,
        kelly_fraction_override=kelly_fraction_override,
    )
