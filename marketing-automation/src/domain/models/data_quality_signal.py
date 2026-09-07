"""Domain model for objective data quality and metric irregularity signals."""

from dataclasses import dataclass
from enum import StrEnum


class DataQualitySignalType(StrEnum):
    """Classification of objective data quality and statistical irregularity signals."""

    ZERO_CONVERSIONS_WITH_ACTIVE_SPEND = "zero_conversions_with_active_spend"
    CTR_STABLE_CONV_COLLAPSE = "ctr_stable_conv_collapse"
    COST_SPIKE_VOLUME_DROP = "cost_spike_volume_drop"
    NEGATIVE_OR_ZERO_METRIC = "negative_or_zero_metric"
    UNUSUAL_VOLUME_SURGE = "unusual_volume_surge"


@dataclass(frozen=True, slots=True)
class DataQualitySignal:
    """Immutable factual signal representing a data quality condition or metric anomaly.

    Contains zero subjective diagnoses or action recommendations.
    """

    signal_type: DataQualitySignalType
    is_triggered: bool
    metric_name: str
    current_value: float | None = None
    baseline_value: float | None = None
    delta_pct: float | None = None
    factual_statement: str = ""
