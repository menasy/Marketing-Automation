"""Z-score statistical calculation engine with defensive handling for edge cases."""

import math
from collections.abc import Sequence


def calculate_z_score(
    current: float,
    mean: float,
    std: float,
    sample_count: int,
    std_threshold: float = 1e-9,
) -> float | None:
    """Calculate Z-Score deviation with strict sample size and variance guards.

    formula: z = (current - mean) / std

    Returns None if:
    - sample_count < 7 (insufficient baseline sample)
    - std <= 0.0 or abs(std) < std_threshold (zero standard deviation / flat line)
    - any parameter is NaN or Infinity
    - calculated z-score is NaN or Infinity
    """
    if sample_count < 7:
        return None

    if (
        math.isnan(current)
        or math.isinf(current)
        or math.isnan(mean)
        or math.isinf(mean)
        or math.isnan(std)
        or math.isinf(std)
    ):
        return None

    if std <= 0.0 or abs(std) < std_threshold:
        return None

    z_score = (current - mean) / std

    if math.isnan(z_score) or math.isinf(z_score):
        return None

    return z_score


def compute_sample_z_score(
    current: float,
    baseline_values: Sequence[float],
    std_threshold: float = 1e-9,
) -> float | None:
    """Compute mean, std, and Z-score from a raw sequence of baseline values."""
    if len(baseline_values) < 7 or math.isnan(current) or math.isinf(current):
        return None

    clean_values: list[float] = []
    for val in baseline_values:
        if math.isnan(val) or math.isinf(val):
            return None
        clean_values.append(val)

    sample_count = len(clean_values)
    if sample_count < 7:
        return None

    mean = sum(clean_values) / sample_count
    variance = sum((x - mean) ** 2 for x in clean_values) / sample_count
    std = math.sqrt(variance)

    return calculate_z_score(
        current=current,
        mean=mean,
        std=std,
        sample_count=sample_count,
        std_threshold=std_threshold,
    )
