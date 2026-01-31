"""
Map composite score (-2..+2) to Model_P in [0.15, 0.85].

Formula (linear): Model_P = 0.15 + (score + 2) / 4 * 0.70
  - score = -2 => 0.15 (max bearish)
  - score =  0 => 0.50 (neutral)
  - score = +2 => 0.85 (max bullish)
Bounds avoid extremes; configurable via constants if needed.
"""


def score_to_model_p(score: float) -> float:
    """Linear map: score in [-2, +2] -> Model_P in [0.15, 0.85]. Clamp at boundaries."""
    if score <= -2:
        return 0.15
    if score >= 2:
        return 0.85
    return round(0.15 + (score + 2) / 4 * 0.70, 4)
