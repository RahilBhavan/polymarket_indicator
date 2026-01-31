"""Edge = Model_P - Market_P_yes. Gate by EDGE_THRESHOLD."""

from app.config import get_settings


def compute_edge(model_p: float, market_p_yes: float) -> float:
    """Edge for YES side: model_p - market_p_yes. Positive = YES underpriced."""
    return round(model_p - market_p_yes, 4)


def edge_above_threshold(edge: float) -> bool:
    """True if edge >= EDGE_THRESHOLD (default 5%)."""
    settings = get_settings()
    return edge >= settings.edge_threshold


def direction_from_edge(
    model_p: float,
    market_p_yes: float,
    market_bid: float | None = None,
) -> tuple[str, float]:
    """
    Return (direction, edge). direction = YES | NO | NO_TRADE.
    If edge_yes >= threshold -> YES; if edge_no >= threshold -> NO; else NO_TRADE.
    edge_yes = model_p - market_p_yes. edge_no = market_bid - model_p (for buying NO).
    """
    edge_yes = compute_edge(model_p, market_p_yes)
    settings = get_settings()
    if edge_yes >= settings.edge_threshold:
        return "YES", edge_yes
    if market_bid is not None:
        edge_no = round(market_bid - model_p, 4)
        if edge_no >= settings.edge_threshold:
            return "NO", edge_no
    return "NO_TRADE", edge_yes
