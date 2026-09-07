"""Domain policy for metric direction classification and anomaly volume guards."""

import math
from dataclasses import dataclass

from src.domain.enums.metric_type import MetricDirection, MetricType


@dataclass(frozen=True, slots=True)
class VolumeGuardConfig:
    """Configurable thresholds for volume guard qualification."""

    min_impressions: float = 100.0
    min_spend: float = 10.0
    min_baseline_conversions: float = 5.0
    zero_conversion_min_spend: float = 50.0


def get_metric_direction(metric_type: MetricType) -> MetricDirection:
    """Return the desired business performance direction for a given metric type.

    Cost metrics (CPA, CPC, CPM): LOWER_IS_BETTER.
    Efficiency metrics (ROAS, CTR): HIGHER_IS_BETTER.
    Volume metrics (Conversions, Conversion Value, Clicks, Impressions): HIGHER_IS_BETTER.
    Spend: NEUTRAL (High increase alone is not automatically a failure without efficiency drop).
    """
    match metric_type:
        case MetricType.CPA | MetricType.CPC | MetricType.CPM:
            return MetricDirection.LOWER_IS_BETTER
        case (
            MetricType.ROAS
            | MetricType.CTR
            | MetricType.CONVERSIONS
            | MetricType.CONVERSION_VALUE
            | MetricType.CLICKS
            | MetricType.IMPRESSIONS
        ):
            return MetricDirection.HIGHER_IS_BETTER
        case MetricType.SPEND:
            return MetricDirection.NEUTRAL


def is_adverse_change(metric_type: MetricType, change_rate: float) -> bool:
    """Evaluate whether a percentage change rate represents an adverse performance shift.

    - LOWER_IS_BETTER: positive change (> 0) is adverse (costs spiked).
    - HIGHER_IS_BETTER: negative change (< 0) is adverse (efficiency/volume dropped).
    - NEUTRAL: change is not inherently adverse on its own.
    """
    if math.isnan(change_rate) or math.isinf(change_rate):
        return False

    direction = get_metric_direction(metric_type)
    if direction == MetricDirection.LOWER_IS_BETTER:
        return change_rate > 0.0
    elif direction == MetricDirection.HIGHER_IS_BETTER:
        return change_rate < 0.0
    return False


def is_volume_significant(
    metric_type: MetricType,
    current_impressions: float,
    current_spend: float,
    current_conversions: float = 0.0,
    baseline_conversions: float = 0.0,
    config: VolumeGuardConfig | None = None,
) -> bool:
    """Determine whether campaign volume is sufficient to evaluate statistical anomalies.

    Filters out false positive anomalies caused by micro-budget noise or
    insufficient conversion events.
    """
    cfg = config or VolumeGuardConfig()

    # Guard against NaN, Inf, or negative inputs
    for val in (
        current_impressions,
        current_spend,
        current_conversions,
        baseline_conversions,
    ):
        if math.isnan(val) or math.isinf(val) or val < 0:
            return False

    # Micro-budget noise guard
    if current_impressions < cfg.min_impressions or current_spend < cfg.min_spend:
        return False

    # Conversion-dependent metric guards (CPA, ROAS, Conversions)
    if metric_type in (MetricType.CPA, MetricType.ROAS, MetricType.CONVERSIONS):
        if baseline_conversions < cfg.min_baseline_conversions:
            return False
        if current_conversions == 0.0 and current_spend < cfg.zero_conversion_min_spend:
            return False

    return True
