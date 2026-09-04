"""Unit tests for z-score calculation math engine."""

from src.infrastructure.anomaly.z_score import (
    calculate_z_score,
    compute_sample_z_score,
)


def test_calculate_z_score_valid() -> None:
    """Valid inputs calculate exact z-score deviation."""
    z = calculate_z_score(
        current=15.0,
        mean=10.0,
        std=2.0,
        sample_count=14,
    )
    assert z == 2.5


def test_calculate_z_score_minimum_sample_count() -> None:
    """Sample count strictly under 7 returns None."""
    assert (
        calculate_z_score(
            current=15.0,
            mean=10.0,
            std=2.0,
            sample_count=6,
        )
        is None
    )

    assert (
        calculate_z_score(
            current=15.0,
            mean=10.0,
            std=2.0,
            sample_count=7,
        )
        == 2.5
    )


def test_calculate_z_score_zero_standard_deviation() -> None:
    """Flatline data with std == 0.0 or below threshold returns None."""
    assert (
        calculate_z_score(
            current=15.0,
            mean=10.0,
            std=0.0,
            sample_count=14,
        )
        is None
    )

    assert (
        calculate_z_score(
            current=15.0,
            mean=10.0,
            std=1e-10,
            sample_count=14,
            std_threshold=1e-9,
        )
        is None
    )


def test_calculate_z_score_nan_and_inf_handling() -> None:
    """NaN or Inf parameters yield None."""
    assert calculate_z_score(float("nan"), 10.0, 2.0, 14) is None
    assert calculate_z_score(15.0, float("inf"), 2.0, 14) is None
    assert calculate_z_score(15.0, 10.0, float("nan"), 14) is None


def test_compute_sample_z_score_valid() -> None:
    """Raw sample baseline list computes mean, std, and Z-score."""
    baseline = [10.0, 12.0, 11.0, 9.0, 10.0, 13.0, 8.0]
    z = compute_sample_z_score(current=16.0, baseline_values=baseline)
    assert z is not None
    assert z > 0.0


def test_compute_sample_z_score_insufficient_values() -> None:
    """Baseline sequences with fewer than 7 observations return None."""
    baseline = [10.0, 12.0, 11.0, 9.0, 10.0]
    assert compute_sample_z_score(current=15.0, baseline_values=baseline) is None


def test_compute_sample_z_score_nan_in_baseline() -> None:
    """Baseline sequences containing NaN return None."""
    baseline = [10.0, 12.0, 11.0, float("nan"), 10.0, 13.0, 8.0]
    assert compute_sample_z_score(current=15.0, baseline_values=baseline) is None
