"""Format signal message (summary and verbose). Max 4096 chars; split if needed."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.config import get_settings
from app.polymarket.selection import is_btc_up_down_hourly_market
from app.signal.engine import SignalResult
from app.signal.engine_15m import Signal15mResult

if TYPE_CHECKING:
    from app.polymarket.models import Market

MAX_MESSAGE_LENGTH = 4096


def _direction_display(result: SignalResult, market: "Market | None") -> str:
    """Show YES/NO as outcome labels (e.g. Up/Down) when market has them."""
    d = result.direction
    if d == "NO_TRADE":
        return d
    if market and market.yes_label and market.no_label:
        return market.yes_label if d == "YES" else market.no_label
    return d


def _header(market: "Market | None") -> str:
    """Header: BTC Hourly Up/Down vs BTC Daily."""
    if market and is_btc_up_down_hourly_market(market):
        return "BTC Hourly Up/Down"
    return "BTC Daily"


def format_signal_summary(
    result: SignalResult,
    missing_sources: list[str] | None = None,
    market: "Market | None" = None,
) -> str:
    """Summary signal message (direction, model confidence %, market price, edge %, rec bet, reasoning, liquidity, generated)."""
    settings = get_settings()
    prefix = "[PAPER] Do not trade with real money.\n\n" if settings.paper_trading else ""
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = _header(market)
    direction_str = _direction_display(result, market)
    msg = (
        prefix + f"<b>SIGNAL: {header}</b>\n"
        f"Direction: {direction_str}\n"
        f"Model confidence: {result.model_p:.0%}\n"
        f"Market price: {result.market_p:.0%}\n"
        f"Edge: {result.edge:+.0%}\n"
        f"Rec. bet: ${result.recommended_usd:.2f}\n"
        f"Reasoning: {result.reasoning_summary}\n"
    )
    if missing_sources:
        msg += f"Missing factors: {', '.join(missing_sources)}\n"
    if result.liquidity_warning:
        msg += f"⚠ {result.liquidity_warning}\n"
    msg += f"Generated: {generated}\n"
    return msg


def format_signal_verbose(
    result: SignalResult,
    missing_sources: list[str] | None = None,
    market: "Market | None" = None,
) -> str:
    """Verbose: add factor breakdown."""
    summary = format_signal_summary(result, missing_sources=missing_sources, market=market)
    lines = ["<b>Factor breakdown</b>"]
    for r in result.reasoning:
        factor = r.get("factor", "?")
        raw = r.get("raw_value", "-")
        contrib = r.get("contribution")
        c = f"{contrib:+.2f}" if contrib is not None else "-"
        stale = " (stale)" if r.get("stale") else ""
        err = f" ({r['error']})" if r.get("error") else ""
        lines.append(f"{factor}: {raw} → {c}{stale}{err}")
    extra = "\n".join(lines)
    if len(summary) + len(extra) + 2 <= MAX_MESSAGE_LENGTH:
        return summary + "\n" + extra
    return summary + "\n(Use /signal for full details)"


def format_signal_message(
    result: SignalResult,
    verbose: bool = False,
    missing_sources: list[str] | None = None,
    market: "Market | None" = None,
) -> str:
    """Single message; truncate if over limit."""
    msg = (
        format_signal_verbose(result, missing_sources=missing_sources, market=market)
        if verbose
        else format_signal_summary(result, missing_sources=missing_sources, market=market)
    )
    if len(msg) > MAX_MESSAGE_LENGTH:
        msg = msg[: MAX_MESSAGE_LENGTH - 20] + "\n...(truncated)"
    return msg


def _hour_label_from_slug(slug: str | None) -> str:
    """Extract hour label from slug (e.g. '5pm-et' from 'bitcoin-up-or-down-january-31-5pm-et')."""
    if not slug:
        return "?"
    parts = slug.split("-")
    for i, p in enumerate(parts):
        if p and ("pm" in p.lower() or "am" in p.lower()):
            suffix = "-" + parts[i + 1] if i + 1 < len(parts) and parts[i + 1] == "et" else ""
            return p + suffix
    return slug[-24:] if len(slug) > 24 else slug


def format_signal_multi_hour(
    markets_results: list[tuple["Market", SignalResult]],
    missing_sources: list[str] | None = None,
) -> str:
    """One message for next N hourly markets: each with hour label, direction, edge, rec bet, link."""
    settings = get_settings()
    prefix = "[PAPER] Do not trade with real money.\n\n" if settings.paper_trading else ""
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        prefix + "<b>BTC Hourly Up/Down – Next {} hours</b>".format(len(markets_results)),
        "Predictions per hour so you can place bets up to 5 hours in advance.",
        "",
    ]
    for market, result in markets_results:
        hour_label = _hour_label_from_slug(market.slug)
        direction_str = _direction_display(result, market)
        line = (
            f"<b>{hour_label}</b> → {direction_str} | "
            f"model {result.model_p:.0%} | market {result.market_p:.0%} | "
            f"edge {result.edge:+.0%} | rec ${result.recommended_usd:.0f}"
        )
        lines.append(line)
        if market.slug:
            lines.append(f"  → https://polymarket.com/event/{market.slug}")
    if missing_sources:
        lines.append("")
        lines.append(f"Missing factors: {', '.join(missing_sources)}")
    lines.append("")
    lines.append(f"Generated: {generated}")
    return "\n".join(lines)


def format_signal_15m_summary(
    result: Signal15mResult,
    market_slug: str | None = None,
) -> str:
    """Summary for BTC 15m Up/Down signal (direction Up/Down/NO_TRADE, phase, rec bet)."""
    settings = get_settings()
    prefix = "[PAPER] Do not trade with real money.\n\n" if settings.paper_trading else ""
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    direction_str = result.direction  # BUY_UP, BUY_DOWN, NO_TRADE
    if direction_str == "BUY_UP":
        direction_str = "Up"
    elif direction_str == "BUY_DOWN":
        direction_str = "Down"
    edge_str = "-"
    if result.edge_up is not None and result.edge_down is not None:
        edge_str = f"Up {result.edge_up:+.0%} / Down {result.edge_down:+.0%}"
    time_left = f"{result.remaining_minutes:.1f}m" if result.remaining_minutes is not None else "-"
    msg = (
        prefix + "<b>SIGNAL: BTC 15m Up/Down</b>\n"
        f"Direction: {direction_str}\n"
        f"Model Up/Down: {result.model_up:.0%} / {result.model_down:.0%}\n"
        f"Market Up/Down: {result.market_up_norm:.0%} / {result.market_down_norm:.0%}\n"
        f"Edge: {edge_str}\n"
        f"Phase: {result.phase} | Time left: {time_left}\n"
        f"Rec. bet: ${result.recommended_usd:.2f}\n"
    )
    if result.reasoning:
        parts = [
            f"{r.get('factor', '?')}={r.get('value', r.get('detail', '-'))}"
            for r in result.reasoning[:5]
        ]
        msg += f"Reasoning: {', '.join(str(p) for p in parts)}\n"
    if result.liquidity_warning:
        msg += f"⚠ {result.liquidity_warning}\n"
    msg += f"Generated: {generated}\n"
    return msg
