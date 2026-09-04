from dataclasses import dataclass
from datetime import date

from src.domain.enums.metric_type import MetricType
from src.domain.enums.platform import Platform


@dataclass(frozen=True, slots=True)
class MetricStats:
    """Statistical metrics computed over a historical window slice."""

    mean: float
    std: float
    median: float
    sample_count: int
    min_value: float
    max_value: float
    insufficient_history: bool = False


@dataclass(frozen=True, slots=True)
class BaselineMetric:
    """Historical baseline statistical profile for a campaign group."""

    platform: Platform
    campaign_name: str
    country: str
    window_start: date
    window_end: date
    metrics: dict[MetricType, MetricStats]
    insufficient_history: bool = False


@dataclass(frozen=True, slots=True)
class CurrentMetric:
    """Observed metric performance snapshot for a specific date."""

    platform: Platform
    campaign_name: str
    country: str
    date: date
    metrics: dict[MetricType, float | None]
    is_low_volume: bool = False
