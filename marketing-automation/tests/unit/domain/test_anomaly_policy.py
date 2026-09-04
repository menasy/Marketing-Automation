"""Unit tests for domain anomaly policy, metric direction rules, and volume guards."""

import math

from src.domain.enums.metric_type import MetricDirection, MetricType
from src.domain.services.anomaly_policy import (
    VolumeGuardConfig,
    get_metric_direction,
    is_adverse_change,
    is_volume_significant,
)


def test_metric_direction_cost_metrics() -> None:
    """Cost metrics (CPA, CPC, CPM) must be classified as LOWER_IS_BETTER."""
    assert get_metric_direction(MetricType.CPA) == MetricDirection.LOWER_IS_BETTER
    assert get_metric_direction(MetricType.CPC) == MetricDirection.LOWER_IS_BETTER
    assert get_metric_direction(MetricType.CPM) == MetricDirection.LOWER_IS_BETTER


def test_metric_direction_efficiency_and_volume_metrics() -> None:
    """Efficiency and volume metrics must be classified as HIGHER_IS_BETTER."""
    assert get_metric_direction(MetricType.ROAS) == MetricDirection.HIGHER_IS_BETTER
    assert get_metric_direction(MetricType.CTR) == MetricDirection.HIGHER_IS_BETTER
    assert get_metric_direction(MetricType.CONVERSIONS) == MetricDirection.HIGHER_IS_BETTER
    assert get_metric_direction(MetricType.CONVERSION_VALUE) == MetricDirection.HIGHER_IS_BETTER
    assert get_metric_direction(MetricType.CLICKS) == MetricDirection.HIGHER_IS_BETTER
    assert get_metric_direction(MetricType.IMPRESSIONS) == MetricDirection.HIGHER_IS_BETTER


def test_metric_direction_spend() -> None:
    """Spend alone must be classified as NEUTRAL."""
    assert get_metric_direction(MetricType.SPEND) == MetricDirection.NEUTRAL


def test_is_adverse_change() -> None:
    """Adverse change detection based on metric direction."""
    # Cost metric: positive change rate (+0.25) is adverse
    assert is_adverse_change(MetricType.CPA, 0.25) is True
    assert is_adverse_change(MetricType.CPA, -0.25) is False

    # Efficiency metric: negative change rate (-0.25) is adverse
    assert is_adverse_change(MetricType.ROAS, -0.25) is True
    assert is_adverse_change(MetricType.ROAS, 0.25) is False

    # Neutral metric: change rate is not adverse alone
    assert is_adverse_change(MetricType.SPEND, 0.50) is False
    assert is_adverse_change(MetricType.SPEND, -0.50) is False

    # Invalid input handling
    assert is_adverse_change(MetricType.CPA, math.nan) is False
    assert is_adverse_change(MetricType.CPA, math.inf) is False


def test_volume_guard_micro_budget_filtering() -> None:
    """Campaigns with low spend or impressions fail volume significance."""
    # Low impressions (< 100)
    assert (
        is_volume_significant(
            metric_type=MetricType.CPC,
            current_impressions=50,
            current_spend=20.0,
        )
        is False
    )

    # Low spend (< $10)
    assert (
        is_volume_significant(
            metric_type=MetricType.CPC,
            current_impressions=500,
            current_spend=5.0,
        )
        is False
    )


def test_volume_guard_low_baseline_conversions() -> None:
    """Conversion metrics fail volume guard if baseline conversions < 5."""
    assert (
        is_volume_significant(
            metric_type=MetricType.CPA,
            current_impressions=1000,
            current_spend=100.0,
            current_conversions=2.0,
            baseline_conversions=3.0,  # < 5 threshold
        )
        is False
    )

    assert (
        is_volume_significant(
            metric_type=MetricType.ROAS,
            current_impressions=1000,
            current_spend=100.0,
            current_conversions=2.0,
            baseline_conversions=4.9,  # < 5 threshold
        )
        is False
    )


def test_volume_guard_zero_conversions_low_spend() -> None:
    """Zero conversions with spend < $50 is ignored to avoid false positive CPA/ROAS spikes."""
    # Current conversions == 0 and spend = $30 (< $50) -> False
    assert (
        is_volume_significant(
            metric_type=MetricType.CPA,
            current_impressions=1000,
            current_spend=30.0,
            current_conversions=0.0,
            baseline_conversions=10.0,
        )
        is False
    )

    # Current conversions == 0 and spend = $60 (>= $50) -> True
    assert (
        is_volume_significant(
            metric_type=MetricType.CPA,
            current_impressions=1000,
            current_spend=60.0,
            current_conversions=0.0,
            baseline_conversions=10.0,
        )
        is True
    )


def test_volume_guard_sufficient_volume() -> None:
    """Sufficient volume qualifies for anomaly evaluation."""
    assert (
        is_volume_significant(
            metric_type=MetricType.CPA,
            current_impressions=5000,
            current_spend=250.0,
            current_conversions=10.0,
            baseline_conversions=12.0,
        )
        is True
    )


def test_volume_guard_nan_and_inf_safety() -> None:
    """Volume guard handles NaN and Inf gracefully by returning False."""
    assert (
        is_volume_significant(
            metric_type=MetricType.CPA,
            current_impressions=float("nan"),
            current_spend=100.0,
        )
        is False
    )
    assert (
        is_volume_significant(
            metric_type=MetricType.CPA,
            current_impressions=1000.0,
            current_spend=float("inf"),
        )
        is False
    )


def test_custom_volume_guard_config() -> None:
    """Custom volume guard config override behavior."""
    custom_cfg = VolumeGuardConfig(
        min_impressions=500.0,
        min_spend=50.0,
        min_baseline_conversions=10.0,
        zero_conversion_min_spend=100.0,
    )
    assert (
        is_volume_significant(
            metric_type=MetricType.CPA,
            current_impressions=300.0,  # fails custom 500
            current_spend=60.0,
            config=custom_cfg,
        )
        is False
    )
