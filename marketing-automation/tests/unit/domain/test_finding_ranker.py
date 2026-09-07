"""Unit tests for FindingRanker pure domain service."""

from src.domain.enums.metric_type import MetricDirection, MetricType
from src.domain.enums.operational import IssueType
from src.domain.enums.platform import Platform
from src.domain.enums.severity import Severity
from src.domain.models.anomaly import AnomalyItem
from src.domain.models.data_quality_signal import DataQualitySignalType
from src.domain.services.finding_ranker import FindingRanker


def test_zero_conversions_ongoing_spend_classified_as_data_quality() -> None:
    """Verify that a drop in conversions to zero with spend is DATA_QUALITY."""
    anomaly_conv = AnomalyItem(
        campaign_name="US_Search_Brand",
        platform=Platform.GOOGLE_ADS,
        country="US",
        metric=MetricType.CONVERSIONS,
        current_value=0.0,
        baseline_value=50.0,
        change_rate=-1.0,
        z_score=-4.5,
        severity=Severity.CRITICAL,
        direction=MetricDirection.HIGHER_IS_BETTER,
        detection_method="z_score",
        rationale="Conversions abruptly dropped to zero.",
    )
    anomaly_spend = AnomalyItem(
        campaign_name="US_Search_Brand",
        platform=Platform.GOOGLE_ADS,
        country="US",
        metric=MetricType.SPEND,
        current_value=200.0,
        baseline_value=195.0,
        change_rate=0.025,
        z_score=0.2,
        severity=Severity.LOW,
        direction=MetricDirection.NEUTRAL,
        detection_method="z_score",
        rationale="Spend continues normally.",
    )

    findings = FindingRanker.rank_findings([anomaly_conv, anomaly_spend])

    assert len(findings) == 1
    finding = findings[0]

    assert finding.campaign_name == "US_Search_Brand"
    assert finding.platform == Platform.GOOGLE_ADS
    assert finding.issue_type == IssueType.DATA_QUALITY
    assert finding.severity == Severity.CRITICAL
    assert "CONVERSIONS" in finding.metric_change
    assert "→" in finding.metric_change
    assert len(finding.data_quality_signals) >= 1

    target_sig_type = DataQualitySignalType.ZERO_CONVERSIONS_WITH_ACTIVE_SPEND
    dq_signal = next(s for s in finding.data_quality_signals if s.signal_type == target_sig_type)
    assert dq_signal.is_triggered is True
    assert "dropped from 50.00 to 0.00" in dq_signal.factual_statement


def test_ctr_collapse_with_rising_cpa_classified_as_performance() -> None:
    """Verify that a collapsing CTR alongside rising CPA is classified as PERFORMANCE."""
    anomaly_ctr = AnomalyItem(
        campaign_name="EU_Retargeting_Meta",
        platform=Platform.META_ADS,
        country="DE",
        metric=MetricType.CTR,
        current_value=0.008,
        baseline_value=0.032,
        change_rate=-0.75,
        z_score=-3.5,
        severity=Severity.HIGH,
        direction=MetricDirection.HIGHER_IS_BETTER,
        detection_method="z_score",
        rationale="CTR collapsed.",
    )
    anomaly_cpa = AnomalyItem(
        campaign_name="EU_Retargeting_Meta",
        platform=Platform.META_ADS,
        country="DE",
        metric=MetricType.CPA,
        current_value=65.0,
        baseline_value=25.0,
        change_rate=1.60,
        z_score=4.2,
        severity=Severity.HIGH,
        direction=MetricDirection.LOWER_IS_BETTER,
        detection_method="z_score",
        rationale="CPA spiked significantly.",
    )

    findings = FindingRanker.rank_findings([anomaly_ctr, anomaly_cpa])

    assert len(findings) == 1
    finding = findings[0]

    assert finding.campaign_name == "EU_Retargeting_Meta"
    assert finding.platform == Platform.META_ADS
    assert finding.issue_type == IssueType.PERFORMANCE
    assert "CTR" in finding.metric_change
    assert "CPA" in finding.metric_change


def test_multiple_anomalies_same_campaign_merged_into_single_finding() -> None:
    """Verify that multiple anomalies for the same campaign are merged into 1 finding."""
    anomalies = [
        AnomalyItem(
            campaign_name="Global_Prospecting",
            platform=Platform.GOOGLE_ADS,
            country="US",
            metric=MetricType.CPA,
            current_value=80.0,
            baseline_value=40.0,
            change_rate=1.0,
            z_score=3.1,
            severity=Severity.HIGH,
            direction=MetricDirection.LOWER_IS_BETTER,
            detection_method="z_score",
            rationale="CPA doubled.",
        ),
        AnomalyItem(
            campaign_name="Global_Prospecting",
            platform=Platform.GOOGLE_ADS,
            country="US",
            metric=MetricType.ROAS,
            current_value=1.1,
            baseline_value=2.8,
            change_rate=-0.607,
            z_score=-3.4,
            severity=Severity.CRITICAL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            detection_method="z_score",
            rationale="ROAS dropped severely.",
        ),
        AnomalyItem(
            campaign_name="Global_Prospecting",
            platform=Platform.GOOGLE_ADS,
            country="US",
            metric=MetricType.CONVERSIONS,
            current_value=10.0,
            baseline_value=35.0,
            change_rate=-0.714,
            z_score=-2.9,
            severity=Severity.MEDIUM,
            direction=MetricDirection.HIGHER_IS_BETTER,
            detection_method="z_score",
            rationale="Conversions down.",
        ),
    ]

    findings = FindingRanker.rank_findings(anomalies)

    assert len(findings) == 1
    finding = findings[0]

    assert finding.campaign_name == "Global_Prospecting"
    assert finding.severity == Severity.CRITICAL
    assert "ROAS" in finding.evidence_summary or "CPA" in finding.evidence_summary
    assert "ROAS" in finding.metric_change or "CPA" in finding.metric_change


def test_ranking_order_highest_business_impact_first_and_capped_at_top_3() -> None:
    """Verify that findings are ranked by severity score descending and capped at top 3."""
    anomalies = [
        AnomalyItem(
            campaign_name="Campaign_Low",
            platform=Platform.META_ADS,
            country="US",
            metric=MetricType.SPEND,
            current_value=15.0,
            baseline_value=10.0,
            change_rate=0.5,
            z_score=1.5,
            severity=Severity.LOW,
            direction=MetricDirection.NEUTRAL,
            detection_method="z_score",
            rationale="Minor spend fluctuation.",
        ),
        AnomalyItem(
            campaign_name="Campaign_Critical_DQ",
            platform=Platform.GOOGLE_ADS,
            country="US",
            metric=MetricType.CONVERSIONS,
            current_value=0.0,
            baseline_value=120.0,
            change_rate=-1.0,
            z_score=-5.0,
            severity=Severity.CRITICAL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            detection_method="z_score",
            rationale="Zero conversions with $1500 spend.",
        ),
        AnomalyItem(
            campaign_name="Campaign_Critical_DQ",
            platform=Platform.GOOGLE_ADS,
            country="US",
            metric=MetricType.SPEND,
            current_value=1500.0,
            baseline_value=1450.0,
            change_rate=0.034,
            z_score=0.3,
            severity=Severity.LOW,
            direction=MetricDirection.NEUTRAL,
            detection_method="z_score",
            rationale="High ongoing spend.",
        ),
        AnomalyItem(
            campaign_name="Campaign_High_Perf",
            platform=Platform.META_ADS,
            country="CA",
            metric=MetricType.CPA,
            current_value=75.0,
            baseline_value=30.0,
            change_rate=1.5,
            z_score=3.8,
            severity=Severity.HIGH,
            direction=MetricDirection.LOWER_IS_BETTER,
            detection_method="z_score",
            rationale="High CPA spike.",
        ),
        AnomalyItem(
            campaign_name="Campaign_Med_Perf",
            platform=Platform.GOOGLE_ADS,
            country="UK",
            metric=MetricType.CTR,
            current_value=0.012,
            baseline_value=0.024,
            change_rate=-0.50,
            z_score=-2.8,
            severity=Severity.MEDIUM,
            direction=MetricDirection.HIGHER_IS_BETTER,
            detection_method="z_score",
            rationale="Moderate CTR drop.",
        ),
    ]

    findings = FindingRanker.rank_findings(anomalies, max_findings=3)

    assert len(findings) == 3
    assert findings[0].campaign_name == "Campaign_Critical_DQ"
    assert findings[1].campaign_name == "Campaign_High_Perf"
    assert findings[2].campaign_name == "Campaign_Med_Perf"
    assert findings[0].score >= findings[1].score >= findings[2].score


def test_empty_anomalies_returns_empty_list() -> None:
    """Verify that passing an empty list returns an empty list."""
    assert FindingRanker.rank_findings([]) == []
