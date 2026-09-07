"""Unit tests for DossierCompiler pure domain service."""

from src.domain.enums.metric_type import MetricDirection, MetricType
from src.domain.enums.platform import Platform
from src.domain.enums.severity import Severity
from src.domain.models.ad_record import NormalizedAdRecord
from src.domain.models.anomaly import AnomalyItem
from src.domain.models.data_quality_signal import DataQualitySignalType
from src.domain.services.dossier_compiler import (
    STANDARD_FUNNEL_METRICS,
    DossierCompiler,
)


def test_compile_dossier_clusters_anomalies_by_campaign() -> None:
    """Verify multiple anomalies for the same campaign group into one CampaignEvidence."""
    cpa_anomaly = AnomalyItem(
        campaign_name="US_Search_Brand",
        platform=Platform.GOOGLE_ADS,
        country="US",
        metric=MetricType.CPA,
        current_value=85.0,
        baseline_value=30.0,
        change_rate=1.833,
        z_score=4.5,
        severity=Severity.CRITICAL,
        direction=MetricDirection.LOWER_IS_BETTER,
        detection_method="z_score",
        rationale="CPA spiked.",
    )
    spend_anomaly = AnomalyItem(
        campaign_name="US_Search_Brand",
        platform=Platform.GOOGLE_ADS,
        country="US",
        metric=MetricType.SPEND,
        current_value=2500.0,
        baseline_value=2400.0,
        change_rate=0.0417,
        z_score=0.3,
        severity=Severity.LOW,
        direction=MetricDirection.NEUTRAL,
        detection_method="z_score",
        rationale="Spend ongoing.",
    )

    dossier = DossierCompiler.compile_dossier(
        anomalies=[cpa_anomaly, spend_anomaly],
        target_date="2026-09-03",
        baseline_window="2026-08-05 to 2026-09-02",
    )

    assert dossier.total_anomalies_detected == 2
    assert dossier.total_campaigns_impacted == 1
    assert len(dossier.top_campaign_evidence) == 1

    ce = dossier.top_campaign_evidence[0]
    assert ce.campaign_name == "US_Search_Brand"
    assert ce.platform == "google_ads"
    assert ce.country == "US"
    assert ce.spend == 2500.0
    # Risk score = Spend (2500) * max_z (4.5) = 11250.0
    assert ce.financial_impact_score == 11250.0


def test_compile_dossier_populates_all_8_metrics() -> None:
    """Verify that every CampaignEvidence has all 8 standard funnel metrics populated."""
    conv_anomaly = AnomalyItem(
        campaign_name="EU_Retargeting_Meta",
        platform=Platform.META_ADS,
        country="DE",
        metric=MetricType.CONVERSIONS,
        current_value=0.0,
        baseline_value=40.0,
        change_rate=-1.0,
        z_score=-4.0,
        severity=Severity.CRITICAL,
        direction=MetricDirection.HIGHER_IS_BETTER,
        detection_method="z_score",
        rationale="Zero conversions.",
    )

    dossier = DossierCompiler.compile_dossier([conv_anomaly])
    assert len(dossier.top_campaign_evidence) == 1

    ce = dossier.top_campaign_evidence[0]
    # Check all 8 metrics exist
    for m_name in STANDARD_FUNNEL_METRICS:
        assert m_name in ce.metrics
        me = ce.metrics[m_name]
        assert me.metric_name == m_name

    # Check conversions metric is flagged as anomaly
    conv_me = ce.metrics["CONVERSIONS"]
    assert conv_me.is_anomaly is True
    assert conv_me.current_value == 0.0
    assert conv_me.baseline_value == 40.0

    # Check non-anomaly metric
    cpa_me = ce.metrics["CPA"]
    assert cpa_me.is_anomaly is False


def test_compile_dossier_binds_data_quality_signals() -> None:
    """Verify DataQualitySignal objects are bound to CampaignEvidence."""
    spend_item = AnomalyItem(
        campaign_name="DQ_Campaign",
        platform=Platform.GOOGLE_ADS,
        country="US",
        metric=MetricType.SPEND,
        current_value=1500.0,
        baseline_value=1450.0,
        change_rate=0.034,
        z_score=0.2,
        severity=Severity.LOW,
        direction=MetricDirection.NEUTRAL,
        detection_method="z_score",
        rationale="Active spend.",
    )
    conv_item = AnomalyItem(
        campaign_name="DQ_Campaign",
        platform=Platform.GOOGLE_ADS,
        country="US",
        metric=MetricType.CONVERSIONS,
        current_value=0.0,
        baseline_value=100.0,
        change_rate=-1.0,
        z_score=-5.0,
        severity=Severity.CRITICAL,
        direction=MetricDirection.HIGHER_IS_BETTER,
        detection_method="z_score",
        rationale="Zero conversions.",
    )

    dossier = DossierCompiler.compile_dossier([spend_item, conv_item])
    ce = dossier.top_campaign_evidence[0]

    assert len(ce.data_quality_signals) >= 1
    dq_types = [s.signal_type for s in ce.data_quality_signals if s.is_triggered]
    assert DataQualitySignalType.ZERO_CONVERSIONS_WITH_ACTIVE_SPEND in dq_types


def test_compile_dossier_ranks_top_n_by_financial_impact() -> None:
    """Verify campaigns order by financial_impact_score descending and cap at max_campaigns."""
    # Campaign 1: Spend 100 * Z 2.0 = 200
    a1 = AnomalyItem(
        campaign_name="Camp_Low",
        platform=Platform.META_ADS,
        country="US",
        metric=MetricType.CPA,
        current_value=40.0,
        baseline_value=20.0,
        change_rate=1.0,
        z_score=2.0,
        severity=Severity.MEDIUM,
        direction=MetricDirection.LOWER_IS_BETTER,
        detection_method="z_score",
        rationale="Low impact.",
    )
    a1_spend = AnomalyItem(
        campaign_name="Camp_Low",
        platform=Platform.META_ADS,
        country="US",
        metric=MetricType.SPEND,
        current_value=100.0,
        baseline_value=100.0,
        change_rate=0.0,
        z_score=0.0,
        severity=Severity.LOW,
        direction=MetricDirection.NEUTRAL,
        detection_method="z_score",
        rationale="Spend.",
    )

    # Campaign 2: Spend 5000 * Z 5.0 = 25000
    a2 = AnomalyItem(
        campaign_name="Camp_High",
        platform=Platform.GOOGLE_ADS,
        country="US",
        metric=MetricType.CPA,
        current_value=150.0,
        baseline_value=30.0,
        change_rate=4.0,
        z_score=5.0,
        severity=Severity.CRITICAL,
        direction=MetricDirection.LOWER_IS_BETTER,
        detection_method="z_score",
        rationale="High impact.",
    )
    a2_spend = AnomalyItem(
        campaign_name="Camp_High",
        platform=Platform.GOOGLE_ADS,
        country="US",
        metric=MetricType.SPEND,
        current_value=5000.0,
        baseline_value=4800.0,
        change_rate=0.041,
        z_score=0.3,
        severity=Severity.LOW,
        direction=MetricDirection.NEUTRAL,
        detection_method="z_score",
        rationale="Spend.",
    )

    dossier = DossierCompiler.compile_dossier(
        anomalies=[a1, a1_spend, a2, a2_spend], max_campaigns=2
    )

    assert len(dossier.top_campaign_evidence) == 2
    assert dossier.top_campaign_evidence[0].campaign_name == "Camp_High"
    assert dossier.top_campaign_evidence[1].campaign_name == "Camp_Low"
    assert (
        dossier.top_campaign_evidence[0].financial_impact_score
        > dossier.top_campaign_evidence[1].financial_impact_score
    )


def test_compile_dossier_uses_records_for_non_anomaly_values() -> None:
    """Verify NormalizedAdRecord values populate non-anomaly metrics."""
    cpa_anomaly = AnomalyItem(
        campaign_name="Record_Campaign",
        platform=Platform.META_ADS,
        country="UK",
        metric=MetricType.CPA,
        current_value=90.0,
        baseline_value=30.0,
        change_rate=2.0,
        z_score=3.8,
        severity=Severity.HIGH,
        direction=MetricDirection.LOWER_IS_BETTER,
        detection_method="z_score",
        rationale="CPA anomaly.",
    )
    record = NormalizedAdRecord(
        date="2026-09-03",
        platform=Platform.META_ADS,
        campaign_name="Record_Campaign",
        country="UK",
        currency="USD",
        spend=3000.0,
        impressions=50000,
        clicks=1500,
        conversions=33.3,
        conversion_value=2997.0,
        ctr=0.03,
        cpc=2.0,
        cpm=60.0,
        cpa=90.0,
        roas=1.0,
    )

    dossier = DossierCompiler.compile_dossier(anomalies=[cpa_anomaly], records=[record])
    ce = dossier.top_campaign_evidence[0]

    assert ce.spend == 3000.0
    assert ce.metrics["IMPRESSIONS"].current_value == 50000.0
    assert ce.metrics["CLICKS"].current_value == 1500.0
    assert ce.metrics["CTR"].current_value == 0.03


def test_compile_dossier_empty_anomalies() -> None:
    """Verify empty anomalies returns empty dossier."""
    dossier = DossierCompiler.compile_dossier([])
    assert dossier.total_anomalies_detected == 0
    assert dossier.total_campaigns_impacted == 0
    assert len(dossier.top_campaign_evidence) == 0
