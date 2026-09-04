"""Immutable domain dataclass representing an operational finding with root-cause analysis."""

from dataclasses import dataclass

from src.domain.enums.metric_type import MetricType
from src.domain.enums.operational import IssueType
from src.domain.enums.platform import Platform
from src.domain.enums.severity import Severity


@dataclass(frozen=True, slots=True)
class OperationalFinding:
    """Immutable domain dataclass representing an operational root-cause finding."""

    campaign_name: str
    platform: Platform
    country: str
    primary_metric: MetricType
    severity: Severity
    issue_type: IssueType
    evidence_summary: str
    business_impact: str
    metric_change: str
    operational_action: str
    budget_action: str
    bid_action: str
    creative_action: str
    tracking_action: str
    score: float
