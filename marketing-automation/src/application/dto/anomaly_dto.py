"""Data transfer object for anomaly serialization and JSON export."""

from pydantic import BaseModel, Field

from src.domain.models.anomaly import AnomalyItem


class AnomalyDTO(BaseModel):
    """Data transfer object for serialized JSON export of detected anomalies."""

    campaign: str = Field(..., description="Campaign name")
    platform: str = Field(..., description="Advertising platform")
    country: str = Field(..., description="Target country code")
    metric: str = Field(..., description="Metric type evaluated")
    current_value: float = Field(..., description="Observed metric value for target date")
    baseline_value: float = Field(..., description="Historical baseline mean value")
    change_rate: float = Field(..., description="Relative percentage change rate")
    z_score: float = Field(..., description="Statistical z-score deviation")
    severity: str = Field(..., description="Classified severity level")
    direction: str = Field(..., description="Metric direction classification")
    detection_method: str = Field(..., description="Detection method used")
    rationale: str = Field(..., description="Human-readable explanation of anomaly")

    @classmethod
    def from_domain(cls, item: AnomalyItem) -> "AnomalyDTO":
        """Convert domain AnomalyItem entity to serialized DTO."""
        return cls(
            campaign=item.campaign_name,
            platform=str(item.platform.value if hasattr(item.platform, "value") else item.platform),
            country=item.country,
            metric=str(item.metric.value if hasattr(item.metric, "value") else item.metric),
            current_value=round(item.current_value, 4),
            baseline_value=round(item.baseline_value, 4),
            change_rate=round(item.change_rate, 4),
            z_score=round(item.z_score, 4),
            severity=str(item.severity.value if hasattr(item.severity, "value") else item.severity),
            direction=str(
                item.direction.value if hasattr(item.direction, "value") else item.direction
            ),
            detection_method=item.detection_method,
            rationale=item.rationale,
        )
