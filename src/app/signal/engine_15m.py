"""Intraday 15m Up/Down signal engine: TA scoring, time-aware edge, Kelly sizing."""

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_settings
from app.logging_config import get_logger
from app.polymarket.models import UpDownQuote
from app.signal.kelly import recommended_size_usd

logger = get_logger(__name__)

BINANCE_KLINES_1M = "https://api.binance.com/api/v3/klines"
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
VWAP_SLOPE_LOOKBACK = 5
CANDLE_WINDOW_MINUTES = 15


@dataclass
class Signal15mResult:
    """Result of 15m signal generation."""

    direction: str  # BUY_UP | BUY_DOWN | NO_TRADE
    model_up: float
    model_down: float
    market_up_norm: float
    market_down_norm: float
    edge_up: float | None
    edge_down: float | None
    recommended_usd: float
    phase: str  # EARLY | MID | LATE
    remaining_minutes: float | None
    reasoning: list[dict[str, Any]]
    liquidity_warning: str | None = None


async def fetch_klines_1m(limit: int = 240) -> list[list[float]]:
    """Fetch 1m klines from Binance. Each row: [open_time, open, high, low, close, volume, ...]."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                BINANCE_KLINES_1M,
                params={"symbol": "BTCUSDT", "interval": "1m", "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("klines_1m_fetch_failed", error=str(e))
        return []
    if not isinstance(data, list):
        return []
    return [c for c in data if isinstance(c, (list, tuple)) and len(c) >= 6]


def _typical_price(candle: list) -> float:
    """(high + low + close) / 3."""
    return (float(candle[2]) + float(candle[3]) + float(candle[4])) / 3


def _session_vwap(candles: list[list[float]]) -> float | None:
    """Cumulative VWAP: sum(typical * volume) / sum(volume)."""
    if not candles:
        return None
    total_pv = 0.0
    total_v = 0.0
    for c in candles:
        tp = _typical_price(c)
        vol = float(c[5])
        total_pv += tp * vol
        total_v += vol
    if total_v <= 0:
        return None
    return total_pv / total_v


def _vwap_series(candles: list[list[float]]) -> list[float]:
    """Cumulative VWAP at each bar."""
    out: list[float] = []
    total_pv = 0.0
    total_v = 0.0
    for c in candles:
        tp = _typical_price(c)
        vol = float(c[5])
        total_pv += tp * vol
        total_v += vol
        if total_v > 0:
            out.append(total_pv / total_v)
        else:
            out.append(tp)
    return out


def _rsi(closes: list[float], period: int = RSI_PERIOD) -> float | None:
    """RSI at last bar."""
    if len(closes) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for i in range(len(closes) - period, len(closes)):
        ch = closes[i] - closes[i - 1]
        if ch > 0:
            gains.append(ch)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-ch)
    avg_gain = sum(gains) / period if gains else 0.0
    avg_loss = sum(losses) / period if losses else 0.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1 + rs))


def _rsi_slope(rsi_series: list[float], n: int = 3) -> float | None:
    """Slope of last n RSI values (linear)."""
    if len(rsi_series) < n:
        return None
    tail = rsi_series[-n:]
    return (tail[-1] - tail[0]) / n if n else None


def _ema(values: list[float], period: int) -> list[float]:
    """EMA series; first value is SMA of first period."""
    if len(values) < period:
        return []
    out: list[float] = []
    mult = 2.0 / (period + 1)
    sma = sum(values[:period]) / period
    out.append(sma)
    for i in range(period, len(values)):
        ema_val = (values[i] - out[-1]) * mult + out[-1]
        out.append(ema_val)
    return out


def _macd(
    closes: list[float],
    fast: int = MACD_FAST,
    slow: int = MACD_SLOW,
    signal: int = MACD_SIGNAL,
) -> tuple[float | None, float | None, float | None]:
    """Return (macd_line, signal_line, histogram) at last bar."""
    if len(closes) < slow + signal:
        return (None, None, None)
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    # Align: macd_line = ema_fast[-(len(ema_slow)):] - ema_slow
    n = len(ema_slow)
    if len(ema_fast) < n:
        return (None, None, None)
    macd_line = [ema_fast[-n + i] - ema_slow[i] for i in range(n)]
    signal_line = _ema(macd_line, signal)
    if len(signal_line) < 1:
        return (None, None, None)
    hist = macd_line[-1] - signal_line[-1]
    return (macd_line[-1], signal_line[-1], hist)


def _heiken_ashi_color(candles: list[list[float]]) -> str | None:
    """Last bar Heiken Ashi color: 'green' or 'red'."""
    if len(candles) < 2:
        return None
    o0, h0, l0, c0 = float(candles[-2][1]), float(candles[-2][2]), float(candles[-2][3]), float(candles[-2][4])
    o1, h1, l1, c1 = float(candles[-1][1]), float(candles[-1][2]), float(candles[-1][3]), float(candles[-1][4])
    ha_c = (o1 + h1 + l1 + c1) / 4
    ha_o = (o0 + c0) / 2
    return "green" if ha_c >= ha_o else "red"


def _heiken_ashi_consecutive_count(candles: list[list[float]]) -> int:
    """Count consecutive same-color HA bars at end."""
    if len(candles) < 2:
        return 0
    colors: list[str] = []
    for i in range(1, len(candles)):
        o0, c0 = float(candles[i - 1][1]), float(candles[i - 1][4])
        o1, h1, l1, c1 = float(candles[i][1]), float(candles[i][2]), float(candles[i][3]), float(candles[i][4])
        ha_c = (o1 + h1 + l1 + c1) / 4
        ha_o = (o0 + c0) / 2
        colors.append("green" if ha_c >= ha_o else "red")
    if not colors:
        return 0
    last = colors[-1]
    n = 0
    for c in reversed(colors):
        if c == last:
            n += 1
        else:
            break
    return n


def _score_direction(
    last_price: float,
    vwap_now: float | None,
    vwap_slope: float | None,
    rsi: float | None,
    rsi_slope: float | None,
    macd_hist: float | None,
    ha_color: str | None,
    ha_count: int,
    failed_vwap_reclaim: bool,
) -> float:
    """
    Score raw probability for UP (0..1). Higher = more bullish.
    Port of JS scoreDirection: up/down scores then rawUp = up/(up+down).
    """
    up = 1.0
    down = 1.0
    if last_price is not None and vwap_now is not None:
        if last_price > vwap_now:
            up += 2
        if last_price < vwap_now:
            down += 2
    if vwap_slope is not None:
        if vwap_slope > 0:
            up += 2
        if vwap_slope < 0:
            down += 2
    if rsi is not None and rsi_slope is not None:
        if rsi > 55 and rsi_slope > 0:
            up += 2
        if rsi < 45 and rsi_slope < 0:
            down += 2
    if macd_hist is not None:
        if macd_hist > 0:
            up += 1
        if macd_hist < 0:
            down += 1
    if ha_color:
        if ha_color == "green" and ha_count >= 2:
            up += 1
        if ha_color == "red" and ha_count >= 2:
            down += 1
    if failed_vwap_reclaim:
        down += 3
    return up / (up + down)


def _apply_time_awareness(raw_up: float, remaining_minutes: float | None, window_minutes: float) -> tuple[float, float]:
    """Decay raw_up toward 0.5 as time runs out. Return (adjusted_up, adjusted_down)."""
    if remaining_minutes is None or remaining_minutes < 0:
        time_decay = 0.0
    else:
        time_decay = min(1.0, max(0.0, remaining_minutes / window_minutes))
    adjusted_up = max(0.0, min(1.0, 0.5 + (raw_up - 0.5) * time_decay))
    return (adjusted_up, 1.0 - adjusted_up)


def _compute_edge_up_down(
    model_up: float,
    model_down: float,
    market_up_norm: float,
    market_down_norm: float,
) -> tuple[float | None, float | None]:
    """Edge for Up and Down: model - market (normalized)."""
    if market_up_norm is None or market_down_norm is None:
        return (None, None)
    edge_up = model_up - market_up_norm
    edge_down = model_down - market_down_norm
    return (round(edge_up, 4), round(edge_down, 4))


def _decide(
    remaining_minutes: float | None,
    edge_up: float | None,
    edge_down: float | None,
    model_up: float,
    model_down: float,
) -> tuple[str, str]:
    """
    Return (direction, phase). direction = BUY_UP | BUY_DOWN | NO_TRADE.
    Phase = EARLY (>10m), MID (5-10m), LATE (<5m). Stricter thresholds later.
    """
    rem = remaining_minutes if remaining_minutes is not None else 10.0
    if rem > 10:
        phase = "EARLY"
        threshold = 0.05
        min_prob = 0.55
    elif rem > 5:
        phase = "MID"
        threshold = 0.10
        min_prob = 0.60
    else:
        phase = "LATE"
        threshold = 0.20
        min_prob = 0.65

    if edge_up is None or edge_down is None:
        return ("NO_TRADE", phase)
    best_side = "BUY_UP" if edge_up > edge_down else "BUY_DOWN"
    best_edge = edge_up if best_side == "BUY_UP" else edge_down
    best_model = model_up if best_side == "BUY_UP" else model_down
    if best_edge < threshold:
        return ("NO_TRADE", phase)
    if best_model < min_prob:
        return ("NO_TRADE", phase)
    return (best_side, phase)


def run_engine_15m(
    quote: UpDownQuote,
    remaining_minutes: float | None,
    bankroll_usd: float,
    candles_1m: list[list[float]],
) -> Signal15mResult:
    """
    Compute 15m signal from 1m klines and Up/Down quote.
    Uses TA (VWAP, RSI, MACD, Heiken Ashi) -> raw_up -> time decay -> edge -> decide -> size.
    """
    reasoning: list[dict[str, Any]] = []
    if len(candles_1m) < RSI_PERIOD + 10:
        return Signal15mResult(
            direction="NO_TRADE",
            model_up=0.5,
            model_down=0.5,
            market_up_norm=quote.market_up_norm,
            market_down_norm=quote.market_down_norm,
            edge_up=None,
            edge_down=None,
            recommended_usd=0.0,
            phase="EARLY",
            remaining_minutes=remaining_minutes,
            reasoning=[{"factor": "klines", "detail": "Insufficient 1m klines"}],
            liquidity_warning=None,
        )

    closes = [float(c[4]) for c in candles_1m]
    last_price = closes[-1]
    vwap_now = _session_vwap(candles_1m)
    vwap_series = _vwap_series(candles_1m)
    vwap_slope = None
    if len(vwap_series) >= VWAP_SLOPE_LOOKBACK:
        vwap_slope = (vwap_series[-1] - vwap_series[-VWAP_SLOPE_LOOKBACK]) / VWAP_SLOPE_LOOKBACK

    rsi = _rsi(closes, RSI_PERIOD)
    rsi_series: list[float] = []
    for i in range(RSI_PERIOD + 1, len(closes) + 1):
        r = _rsi(closes[:i], RSI_PERIOD)
        if r is not None:
            rsi_series.append(r)
    rsi_slope = _rsi_slope(rsi_series, 3) if rsi_series else None

    _, _, macd_hist = _macd(closes, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    ha_color = _heiken_ashi_color(candles_1m)
    ha_count = _heiken_ashi_consecutive_count(candles_1m)

    failed_vwap_reclaim = False
    if vwap_now is not None and len(vwap_series) >= 3:
        if closes[-1] < vwap_now and closes[-2] > vwap_series[-2]:
            failed_vwap_reclaim = True

    raw_up = _score_direction(
        last_price,
        vwap_now,
        vwap_slope,
        rsi,
        rsi_slope,
        macd_hist,
        ha_color,
        ha_count,
        failed_vwap_reclaim,
    )
    model_up, model_down = _apply_time_awareness(raw_up, remaining_minutes, float(CANDLE_WINDOW_MINUTES))

    edge_up, edge_down = _compute_edge_up_down(
        model_up,
        model_down,
        quote.market_up_norm,
        quote.market_down_norm,
    )
    direction, phase = _decide(remaining_minutes, edge_up, edge_down, model_up, model_down)

    recommended_usd = 0.0
    liquidity_warning = None
    if direction == "BUY_UP":
        recommended_usd = recommended_size_usd(
            model_up,
            quote.market_up_norm,
            bankroll_usd,
            quote.max_safe_up_usd,
        )
        if quote.max_safe_up_usd < 100 or recommended_usd >= quote.max_safe_up_usd * 0.99:
            liquidity_warning = f"Thin liquidity (Up). Max safe: ${quote.max_safe_up_usd:.0f}"
    elif direction == "BUY_DOWN":
        price_no = max(0.01, min(0.99, quote.market_down_norm))
        recommended_usd = recommended_size_usd(
            model_down,
            price_no,
            bankroll_usd,
            quote.max_safe_down_usd,
        )
        if quote.max_safe_down_usd < 100 or recommended_usd >= quote.max_safe_down_usd * 0.99:
            liquidity_warning = f"Thin liquidity (Down). Max safe: ${quote.max_safe_down_usd:.0f}"

    reasoning.append({"factor": "raw_up", "value": round(raw_up, 3)})
    reasoning.append({"factor": "model_up", "value": round(model_up, 3)})
    if edge_up is not None:
        reasoning.append({"factor": "edge_up", "value": edge_up})
    if edge_down is not None:
        reasoning.append({"factor": "edge_down", "value": edge_down})
    reasoning.append({"factor": "phase", "value": phase})

    return Signal15mResult(
        direction=direction,
        model_up=model_up,
        model_down=model_down,
        market_up_norm=quote.market_up_norm,
        market_down_norm=quote.market_down_norm,
        edge_up=edge_up,
        edge_down=edge_down,
        recommended_usd=recommended_usd,
        phase=phase,
        remaining_minutes=remaining_minutes,
        reasoning=reasoning,
        liquidity_warning=liquidity_warning,
    )
