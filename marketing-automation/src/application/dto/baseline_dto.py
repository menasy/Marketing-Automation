from dataclasses import dataclass
from datetime import date

from src.domain.enums.platform import Platform
from src.domain.models.metric import BaselineMetric, CurrentMetric


@dataclass(frozen=True, slots=True)
class BaselineDatasetDTO:
    """DTO carrying target date, aligned current vs baseline metrics, and analysis metadata."""

    target_date: date
    current_metrics: list[CurrentMetric]
    baseline_metrics: dict[tuple[Platform, str, str], BaselineMetric]
    total_campaigns_analyzed: int
    excluded_new_campaigns_count: int
    low_volume_campaigns_count: int
