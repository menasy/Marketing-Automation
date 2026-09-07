"""Severity classification policy engine for statistical performance anomalies."""

import math

from src.domain.enums.metric_type import MetricType
from src.domain.enums.severity import Severity


def classify_severity(
    metric_type: MetricType,
    z_score: float | None,
    change_rate: float | None,
) -> Severity | None:
    """Classify anomaly severity based on z-score deviation, percentage change, and metric type.

    Threshold Rules:
    - CRITICAL:
        1. (|z| >= 3.0 AND |change| >= 50%)
        2. ROAS drop > 60% (change_rate <= -0.60)
        3. CPA jump > 100% (change_rate >= 1.00)
    - HIGH:
        1. |z| >= 3.0 OR |change| >= 50%
    - MEDIUM:
        1. |z| >= 2.5 OR |change| >= 30%
    - LOW:
        1. |z| >= 2.0 OR |change| >= 20%
    - None: below LOW threshold
    """
    abs_z = (
        abs(z_score)
        if (z_score is not None and not math.isnan(z_score) and not math.isinf(z_score))
        else 0.0
    )
    abs_change = (
        abs(change_rate)
        if (change_rate is not None and not math.isnan(change_rate) and not math.isinf(change_rate))
        else 0.0
    )

    if change_rate is not None and not math.isnan(change_rate) and not math.isinf(change_rate):
        # Specific metric critical conditions
        if metric_type == MetricType.ROAS and change_rate <= -0.60:
            return Severity.CRITICAL
        if metric_type == MetricType.CPA and change_rate >= 1.00:
            return Severity.CRITICAL

    # CRITICAL combined threshold
    if abs_z >= 3.0 and abs_change >= 0.50:
        return Severity.CRITICAL

    # HIGH threshold
    if abs_z >= 3.0 or abs_change >= 0.50:
        return Severity.HIGH

    # MEDIUM threshold
    if abs_z >= 2.5 or abs_change >= 0.30:
        return Severity.MEDIUM

    # LOW threshold
    if abs_z >= 2.0 or abs_change >= 0.20:
        return Severity.LOW

    return None


def generate_rationale(
    metric_type: MetricType,
    current_value: float,
    baseline_value: float,
    change_rate: float | None,
    z_score: float | None,
    severity: Severity,
) -> str:
    """Generate human-readable rationale explanation for a detected anomaly."""
    metric_str = metric_type.value.upper()
    change_pct = f"{change_rate * 100:+.1f}%" if change_rate is not None else "N/A"
    z_str = f"{z_score:+.2f}" if z_score is not None else "N/A"
    sev_str = severity.value.upper()

    if change_rate is not None and change_rate > 0:
        action_word = "spiked"
    elif change_rate is not None and change_rate < 0:
        action_word = "dropped"
    else:
        action_word = "deviated"

    return (
        f"{metric_str} {action_word} by {change_pct} "
        f"(current: {current_value:.2f}, baseline: {baseline_value:.2f}, "
        f"z-score: {z_str}) [{sev_str}]"
    )
