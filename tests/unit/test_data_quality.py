"""Unit tests for DataQualityAnalyzer pure domain service."""

from src.domain.enums.metric_type import MetricDirection, MetricType
from src.domain.enums.platform import Platform
from src.domain.enums.severity import Severity
from src.domain.models.anomaly import AnomalyItem
from src.domain.models.data_quality_signal import DataQualitySignalType
from src.domain.services.data_quality import DataQualityAnalyzer


def test_zero_conversions_with_active_spend_triggered() -> None:
    """Verify ZERO_CONVERSIONS_WITH_ACTIVE_SPEND signal triggers when active spend > $50."""
    spend_item = AnomalyItem(
        campaign_name="Test_Campaign",
        platform=Platform.GOOGLE_ADS,
        country="US",
        metric=MetricType.SPEND,
        current_value=1200.0,
        baseline_value=1150.0,
        change_rate=0.043,
        z_score=0.3,
        severity=Severity.LOW,
        direction=MetricDirection.NEUTRAL,
        detection_method="z_score",
        rationale="Spend ongoing.",
    )
    conv_item = AnomalyItem(
        campaign_name="Test_Campaign",
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
        rationale="Conversions zero.",
    )

    signals = DataQualityAnalyzer.analyze_campaign_signals([spend_item, conv_item])

    triggered_types = [s.signal_type for s in signals if s.is_triggered]
    target_type = DataQualitySignalType.ZERO_CONVERSIONS_WITH_ACTIVE_SPEND
    assert target_type in triggered_types

    dq_signal = next(s for s in signals if s.signal_type == target_type)
    assert dq_signal.current_value == 0.0
    assert dq_signal.baseline_value == 50.0
    assert dq_signal.delta_pct == -100.0
    assert "$1,200.00" in dq_signal.factual_statement
    assert "dropped from 50.00 to 0.00" in dq_signal.factual_statement
    assert "tracking" not in dq_signal.factual_statement.lower()
    assert "bozuldu" not in dq_signal.factual_statement.lower()


def test_ctr_stable_conv_collapse_triggered() -> None:
    """Verify CTR_STABLE_CONV_COLLAPSE triggers when CTR is stable and conversions collapse."""
    ctr_item = AnomalyItem(
        campaign_name="Meta_Brand",
        platform=Platform.META_ADS,
        country="DE",
        metric=MetricType.CTR,
        current_value=0.035,
        baseline_value=0.036,
        change_rate=-0.027,
        z_score=-0.2,
        severity=Severity.LOW,
        direction=MetricDirection.HIGHER_IS_BETTER,
        detection_method="z_score",
        rationale="CTR stable.",
    )
    conv_item = AnomalyItem(
        campaign_name="Meta_Brand",
        platform=Platform.META_ADS,
        country="DE",
        metric=MetricType.CONVERSIONS,
        current_value=15.0,
        baseline_value=80.0,
        change_rate=-0.8125,
        z_score=-4.0,
        severity=Severity.CRITICAL,
        direction=MetricDirection.HIGHER_IS_BETTER,
        detection_method="z_score",
        rationale="Conversions collapsed.",
    )

    signals = DataQualityAnalyzer.analyze_campaign_signals([ctr_item, conv_item])

    triggered_types = [s.signal_type for s in signals if s.is_triggered]
    target_type = DataQualitySignalType.CTR_STABLE_CONV_COLLAPSE
    assert target_type in triggered_types

    signal = next(s for s in signals if s.signal_type == target_type)
    assert "CTR change is stable" in signal.factual_statement


def test_cost_spike_volume_drop_triggered() -> None:
    """Verify COST_SPIKE_VOLUME_DROP triggers when spend and CPA spike with stable volume."""
    spend_item = AnomalyItem(
        campaign_name="Search_Generic",
        platform=Platform.GOOGLE_ADS,
        country="UK",
        metric=MetricType.SPEND,
        current_value=5000.0,
        baseline_value=3000.0,
        change_rate=0.667,
        z_score=3.5,
        severity=Severity.HIGH,
        direction=MetricDirection.NEUTRAL,
        detection_method="z_score",
        rationale="Spend spiked.",
    )
    cpa_item = AnomalyItem(
        campaign_name="Search_Generic",
        platform=Platform.GOOGLE_ADS,
        country="UK",
        metric=MetricType.CPA,
        current_value=120.0,
        baseline_value=60.0,
        change_rate=1.0,
        z_score=4.1,
        severity=Severity.CRITICAL,
        direction=MetricDirection.LOWER_IS_BETTER,
        detection_method="z_score",
        rationale="CPA doubled.",
    )
    imp_item = AnomalyItem(
        campaign_name="Search_Generic",
        platform=Platform.GOOGLE_ADS,
        country="UK",
        metric=MetricType.IMPRESSIONS,
        current_value=100000.0,
        baseline_value=95000.0,
        change_rate=0.052,
        z_score=0.4,
        severity=Severity.LOW,
        direction=MetricDirection.HIGHER_IS_BETTER,
        detection_method="z_score",
        rationale="Impressions up slightly.",
    )

    signals = DataQualityAnalyzer.analyze_campaign_signals([spend_item, cpa_item, imp_item])

    triggered_types = [s.signal_type for s in signals if s.is_triggered]
    assert DataQualitySignalType.COST_SPIKE_VOLUME_DROP in triggered_types


def test_negative_or_zero_metric_triggered() -> None:
    """Verify NEGATIVE_OR_ZERO_METRIC triggers on negative metric values."""
    neg_item = AnomalyItem(
        campaign_name="Invalid_Metric_Campaign",
        platform=Platform.META_ADS,
        country="FR",
        metric=MetricType.CONVERSION_VALUE,
        current_value=-150.0,
        baseline_value=500.0,
        change_rate=-1.30,
        z_score=-5.0,
        severity=Severity.CRITICAL,
        direction=MetricDirection.HIGHER_IS_BETTER,
        detection_method="z_score",
        rationale="Negative conversion value detected.",
    )

    signals = DataQualityAnalyzer.analyze_campaign_signals([neg_item])

    triggered_types = [s.signal_type for s in signals if s.is_triggered]
    assert DataQualitySignalType.NEGATIVE_OR_ZERO_METRIC in triggered_types


def test_empty_anomalies_returns_empty_signals() -> None:
    """Verify empty anomaly list returns empty signals list."""
    assert DataQualityAnalyzer.analyze_campaign_signals([]) == []


def test_zero_spend_does_not_trigger_zero_conversion_signal() -> None:
    """Verify zero conversions with zero spend does not trigger signal."""
    spend_item = AnomalyItem(
        campaign_name="Paused_Campaign",
        platform=Platform.GOOGLE_ADS,
        country="US",
        metric=MetricType.SPEND,
        current_value=0.0,
        baseline_value=0.0,
        change_rate=0.0,
        z_score=0.0,
        severity=Severity.LOW,
        direction=MetricDirection.NEUTRAL,
        detection_method="z_score",
        rationale="Zero spend.",
    )
    conv_item = AnomalyItem(
        campaign_name="Paused_Campaign",
        platform=Platform.GOOGLE_ADS,
        country="US",
        metric=MetricType.CONVERSIONS,
        current_value=0.0,
        baseline_value=10.0,
        change_rate=-1.0,
        z_score=-2.0,
        severity=Severity.MEDIUM,
        direction=MetricDirection.HIGHER_IS_BETTER,
        detection_method="z_score",
        rationale="Zero conversions.",
    )

    signals = DataQualityAnalyzer.analyze_campaign_signals([spend_item, conv_item])
    triggered_types = [s.signal_type for s in signals if s.is_triggered]
    target_type = DataQualitySignalType.ZERO_CONVERSIONS_WITH_ACTIVE_SPEND
    assert target_type not in triggered_types
