"""Unit tests for severity classification policy and rationale generator."""

from src.domain.enums.metric_type import MetricType
from src.domain.enums.severity import Severity
from src.infrastructure.anomaly.severity import (
    classify_severity,
    generate_rationale,
)


def test_classify_severity_critical() -> None:
    """Test CRITICAL severity triggers for combined z & change and metric specific drops/spikes."""
    # 1. Combined z >= 3.0 and change >= 50%
    assert (
        classify_severity(metric_type=MetricType.CPC, z_score=3.2, change_rate=0.55)
        == Severity.CRITICAL
    )

    # 2. ROAS drop > 60% (change_rate <= -0.60)
    assert (
        classify_severity(metric_type=MetricType.ROAS, z_score=-1.5, change_rate=-0.65)
        == Severity.CRITICAL
    )

    # 3. CPA jump > 100% (change_rate >= 1.00)
    assert (
        classify_severity(metric_type=MetricType.CPA, z_score=2.1, change_rate=1.20)
        == Severity.CRITICAL
    )


def test_classify_severity_high() -> None:
    """Test HIGH severity for z >= 3.0 OR change >= 50%."""
    # z >= 3.0 with lower change
    assert (
        classify_severity(metric_type=MetricType.CPC, z_score=3.1, change_rate=0.15)
        == Severity.HIGH
    )

    # change >= 50% with lower z
    assert (
        classify_severity(metric_type=MetricType.CPC, z_score=1.5, change_rate=0.52)
        == Severity.HIGH
    )


def test_classify_severity_medium() -> None:
    """Test MEDIUM severity for z >= 2.5 OR change >= 30%."""
    # z >= 2.5
    assert (
        classify_severity(metric_type=MetricType.CTR, z_score=2.6, change_rate=-0.15)
        == Severity.MEDIUM
    )

    # change >= 30%
    assert (
        classify_severity(metric_type=MetricType.CTR, z_score=1.8, change_rate=-0.35)
        == Severity.MEDIUM
    )


def test_classify_severity_low() -> None:
    """Test LOW severity for z >= 2.0 OR change >= 20%."""
    # z >= 2.0
    assert (
        classify_severity(metric_type=MetricType.CPM, z_score=2.1, change_rate=0.10) == Severity.LOW
    )

    # change >= 20%
    assert (
        classify_severity(metric_type=MetricType.CPM, z_score=1.2, change_rate=0.22) == Severity.LOW
    )


def test_classify_severity_sub_threshold() -> None:
    """Test below LOW threshold yields None."""
    assert classify_severity(metric_type=MetricType.CPA, z_score=1.5, change_rate=0.15) is None


def test_generate_rationale_formatting() -> None:
    """Test rationale output string format."""
    rationale = generate_rationale(
        metric_type=MetricType.CPA,
        current_value=45.0,
        baseline_value=20.0,
        change_rate=1.25,
        z_score=3.42,
        severity=Severity.CRITICAL,
    )
    assert "CPA spiked by +125.0%" in rationale
    assert "current: 45.00" in rationale
    assert "baseline: 20.00" in rationale
    assert "z-score: +3.42" in rationale
    assert "[CRITICAL]" in rationale
