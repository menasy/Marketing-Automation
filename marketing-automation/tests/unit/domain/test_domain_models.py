from dataclasses import FrozenInstanceError

import pytest

from src.domain.enums import MetricDirection, MetricType, Platform, Severity
from src.domain.exceptions import (
    AnomalyCalculationError,
    DomainException,
    InsufficientDataError,
    LLMValidationError,
    NormalizationError,
)
from src.domain.models import (
    AnomalyItem,
    ExecutiveBriefing,
    NormalizedAdRecord,
    PipelineResult,
)


def test_platform_enum_values() -> None:
    """Verify Platform StrEnum values."""
    assert Platform.GOOGLE_ADS.value == "google_ads"
    assert Platform.META_ADS.value == "meta_ads"


def test_metric_type_enum_values() -> None:
    """Verify MetricType and MetricDirection StrEnum values."""
    assert MetricType.SPEND.value == "spend"
    assert MetricType.ROAS.value == "roas"
    assert MetricDirection.HIGHER_IS_BETTER.value == "higher_is_better"
    assert MetricDirection.LOWER_IS_BETTER.value == "lower_is_better"
    assert MetricDirection.NEUTRAL.value == "neutral"


def test_severity_enum_values() -> None:
    """Verify Severity StrEnum values."""
    assert Severity.LOW.value == "low"
    assert Severity.CRITICAL.value == "critical"


def test_normalized_ad_record_instantiation_and_immutability() -> None:
    """Verify NormalizedAdRecord instantiation and frozen immutability."""
    record = NormalizedAdRecord(
        date="2026-09-01",
        platform=Platform.GOOGLE_ADS,
        campaign_name="Search_Brand_US",
        country="US",
        currency="USD",
        spend=150.50,
        impressions=1000,
        clicks=50,
        conversions=5.0,
        conversion_value=250.00,
        ctr=0.05,
        cpc=3.01,
    )

    assert record.date == "2026-09-01"
    assert record.platform == Platform.GOOGLE_ADS
    assert record.spend == 150.50
    assert record.ctr == 0.05
    assert record.roas is None  # Defensive optional rate defaults to None

    with pytest.raises((FrozenInstanceError, AttributeError)):
        record.spend = 200.0  # type: ignore[misc]


def test_anomaly_item_instantiation_and_immutability() -> None:
    """Verify AnomalyItem instantiation and frozen immutability."""
    anomaly = AnomalyItem(
        campaign_name="Meta_Retargeting_DE",
        platform=Platform.META_ADS,
        country="DE",
        metric=MetricType.CPA,
        current_value=45.0,
        baseline_value=20.0,
        change_rate=1.25,
        z_score=2.8,
        severity=Severity.HIGH,
        direction=MetricDirection.LOWER_IS_BETTER,
        detection_method="rolling_zscore",
        rationale="CPA spiked 125% over 14-day baseline",
    )

    assert anomaly.campaign_name == "Meta_Retargeting_DE"
    assert anomaly.metric == MetricType.CPA
    assert anomaly.severity == Severity.HIGH
    assert anomaly.z_score == 2.8

    with pytest.raises((FrozenInstanceError, AttributeError)):
        anomaly.z_score = 4.0  # type: ignore[misc]


def test_executive_briefing_instantiation() -> None:
    """Verify ExecutiveBriefing instantiation and default fields."""
    briefing = ExecutiveBriefing(
        summary="Weekly Ad Spend & Anomaly Overview",
        raw_markdown="# Executive Briefing\nNo critical anomalies observed.",
        critical_findings=["Meta CPA increased by 125%"],
        recommended_actions=["Pause high-cost ad sets"],
    )

    assert briefing.summary == "Weekly Ad Spend & Anomaly Overview"
    assert len(briefing.critical_findings) == 1
    assert len(briefing.recommended_actions) == 1


def test_pipeline_result_instantiation() -> None:
    """Verify PipelineResult instantiation."""
    result = PipelineResult(
        execution_id="exec-12345",
        status="success",
        anomalies_count=3,
        execution_time_seconds=1.45,
        output_paths={"briefing": "/path/to/briefing.md"},
    )

    assert result.execution_id == "exec-12345"
    assert result.status == "success"
    assert result.anomalies_count == 3
    assert result.output_paths["briefing"] == "/path/to/briefing.md"


def test_custom_domain_exceptions_hierarchy() -> None:
    """Verify inheritance hierarchy of custom domain exceptions."""
    assert issubclass(NormalizationError, DomainException)
    assert issubclass(InsufficientDataError, DomainException)
    assert issubclass(AnomalyCalculationError, DomainException)
    assert issubclass(LLMValidationError, DomainException)
    assert issubclass(DomainException, Exception)

    with pytest.raises(DomainException):
        raise NormalizationError("Invalid data format")
