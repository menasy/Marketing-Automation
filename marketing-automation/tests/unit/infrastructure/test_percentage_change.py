"""Unit tests for percentage change calculation math engine."""

from src.infrastructure.anomaly.percentage_change import calculate_percentage_change


def test_calculate_percentage_change_valid() -> None:
    """Valid positive and negative percentage changes."""
    assert calculate_percentage_change(current=150.0, baseline=100.0) == 0.50
    assert calculate_percentage_change(current=50.0, baseline=100.0) == -0.50


def test_calculate_percentage_change_zero_baseline() -> None:
    """Zero or near-zero baseline returns None to prevent division by zero."""
    assert calculate_percentage_change(current=10.0, baseline=0.0) is None
    assert calculate_percentage_change(current=10.0, baseline=1e-10) is None


def test_calculate_percentage_change_nan_and_inf() -> None:
    """NaN or Inf values return None."""
    assert calculate_percentage_change(current=float("nan"), baseline=100.0) is None
    assert calculate_percentage_change(current=100.0, baseline=float("inf")) is None
