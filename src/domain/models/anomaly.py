from dataclasses import dataclass

from src.domain.enums.metric_type import MetricDirection, MetricType
from src.domain.enums.platform import Platform
from src.domain.enums.severity import Severity


@dataclass(frozen=True, slots=True)
class AnomalyItem:
    """Immutable domain entity representing a detected statistical performance anomaly."""

    campaign_name: str
    platform: Platform
    country: str
    metric: MetricType
    current_value: float
    baseline_value: float
    change_rate: float
    z_score: float
    severity: Severity
    direction: MetricDirection
    detection_method: str
    rationale: str
