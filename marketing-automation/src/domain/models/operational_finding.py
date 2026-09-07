"""Immutable domain dataclass representing an operational finding."""

from dataclasses import dataclass, field

from src.domain.enums.metric_type import MetricType
from src.domain.enums.operational import IssueType
from src.domain.enums.platform import Platform
from src.domain.enums.severity import Severity
from src.domain.models.data_quality_signal import DataQualitySignal


@dataclass(frozen=True, slots=True)
class OperationalFinding:
    """Immutable domain dataclass representing a grouped campaign anomaly finding."""

    campaign_name: str
    platform: Platform
    country: str
    primary_metric: MetricType
    severity: Severity
    issue_type: IssueType
    evidence_summary: str
    business_impact: str
    metric_change: str
    score: float
    data_quality_signals: tuple[DataQualitySignal, ...] = field(default_factory=tuple)
    operational_action: str = ""
    budget_action: str = ""
    bid_action: str = ""
    creative_action: str = ""
    tracking_action: str = ""
