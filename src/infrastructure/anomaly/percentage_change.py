"""Percentage change calculation engine with defensive zero-baseline guards."""

import math


def calculate_percentage_change(current: float, baseline: float) -> float | None:
    """Calculate percentage change rate relative to baseline.

    formula: change_rate = (current - baseline) / |baseline|

    Returns None if:
    - baseline == 0.0 (insufficient baseline denominator)
    - abs(baseline) < 1e-9
    - current or baseline is NaN or Infinity
    - calculated change rate is NaN or Infinity
    """
    if math.isnan(current) or math.isinf(current) or math.isnan(baseline) or math.isinf(baseline):
        return None

    abs_baseline = abs(baseline)
    if abs_baseline == 0.0 or abs_baseline < 1e-9:
        return None

    change_rate = (current - baseline) / abs_baseline

    if math.isnan(change_rate) or math.isinf(change_rate):
        return None

    return change_rate
