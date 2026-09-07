"""Domain models for evidence dossier compilation and campaign-level anomaly synthesis."""

from dataclasses import dataclass, field

from src.domain.models.data_quality_signal import DataQualitySignal


@dataclass(frozen=True, slots=True)
class MetricEvidence:
    """Immutable representation of evidence for a single performance metric."""

    metric_name: str
    current_value: float | None = None
    baseline_value: float | None = None
    delta_pct: float | None = None
    z_score: float | None = None
    is_anomaly: bool = False


@dataclass(frozen=True, slots=True)
class CampaignEvidence:
    """Immutable representation of compiled multi-metric evidence for a single campaign entity."""

    campaign_id: str
    campaign_name: str
    platform: str
    account_id: str
    country: str
    spend: float
    financial_impact_score: float
    metrics: dict[str, MetricEvidence]
    data_quality_signals: tuple[DataQualitySignal, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EvidenceDossier:
    """Immutable evidence dossier contract encapsulating top campaign cases for AI reasoning."""

    target_date: str
    baseline_window: str
    total_anomalies_detected: int
    total_campaigns_impacted: int
    top_campaign_evidence: tuple[CampaignEvidence, ...] = field(default_factory=tuple)
