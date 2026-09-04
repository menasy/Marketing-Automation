from typing import cast

from src.domain.enums.platform import Platform
from src.domain.models.ad_record import NormalizedAdRecord
from src.domain.services.metric_calculator import MetricCalculator


def test_calculate_ctr_valid() -> None:
    """Test CTR calculation with valid inputs."""
    assert MetricCalculator.calculate_ctr(50, 1000) == 0.05
    # 123 / 4567 = 0.026932... -> 0.0269
    assert MetricCalculator.calculate_ctr(123, 4567) == 0.0269


def test_calculate_ctr_zero_or_invalid() -> None:
    """Test CTR returns None for zero/negative impressions or invalid inputs."""
    assert MetricCalculator.calculate_ctr(0, 0) is None
    assert MetricCalculator.calculate_ctr(50, 0) is None
    assert MetricCalculator.calculate_ctr(50, -100) is None
    assert MetricCalculator.calculate_ctr(-10, 100) is None
    assert MetricCalculator.calculate_ctr(cast(int, None), 100) is None
    assert MetricCalculator.calculate_ctr(50, cast(int, None)) is None


def test_calculate_cpc_valid() -> None:
    """Test CPC calculation with valid inputs."""
    assert MetricCalculator.calculate_cpc(100.0, 50) == 2.0
    # 100.5 / 3 = 33.5
    assert MetricCalculator.calculate_cpc(100.5, 3) == 33.5
    # 100.0 / 3 = 33.333... -> 33.33
    assert MetricCalculator.calculate_cpc(100.0, 3) == 33.33


def test_calculate_cpc_zero_or_invalid() -> None:
    """Test CPC returns None for zero/negative clicks or invalid inputs."""
    assert MetricCalculator.calculate_cpc(100.0, 0) is None
    assert MetricCalculator.calculate_cpc(100.0, -5) is None
    assert MetricCalculator.calculate_cpc(-50.0, 10) is None
    assert MetricCalculator.calculate_cpc(float("nan"), 10) is None
    assert MetricCalculator.calculate_cpc(float("inf"), 10) is None


def test_calculate_cpm_valid() -> None:
    """Test CPM calculation with valid inputs."""
    assert MetricCalculator.calculate_cpm(150.0, 10000) == 15.0
    # (250.75 / 12345) * 1000 = 20.31186... -> 20.31
    assert MetricCalculator.calculate_cpm(250.75, 12345) == 20.31


def test_calculate_cpm_zero_or_invalid() -> None:
    """Test CPM returns None for zero/negative impressions or invalid inputs."""
    assert MetricCalculator.calculate_cpm(100.0, 0) is None
    assert MetricCalculator.calculate_cpm(100.0, -1000) is None
    assert MetricCalculator.calculate_cpm(-10.0, 1000) is None
    assert MetricCalculator.calculate_cpm(float("nan"), 1000) is None


def test_calculate_cpa_valid() -> None:
    """Test CPA calculation with valid inputs."""
    assert MetricCalculator.calculate_cpa(500.0, 25.0) == 20.0
    # 500.0 / 3.0 = 166.666... -> 166.67
    assert MetricCalculator.calculate_cpa(500.0, 3.0) == 166.67


def test_calculate_cpa_zero_or_invalid() -> None:
    """Test CPA returns None for zero/negative conversions or invalid inputs."""
    assert MetricCalculator.calculate_cpa(500.0, 0.0) is None
    assert MetricCalculator.calculate_cpa(500.0, -2.0) is None
    assert MetricCalculator.calculate_cpa(-100.0, 5.0) is None
    assert MetricCalculator.calculate_cpa(float("inf"), 5.0) is None


def test_calculate_roas_valid() -> None:
    """Test ROAS calculation with valid inputs."""
    assert MetricCalculator.calculate_roas(2000.0, 500.0) == 4.0
    # 1234.56 / 789.10 = 1.56451... -> 1.56
    assert MetricCalculator.calculate_roas(1234.56, 789.10) == 1.56


def test_calculate_roas_zero_or_invalid() -> None:
    """Test ROAS returns None for zero/negative spend or invalid inputs."""
    assert MetricCalculator.calculate_roas(1000.0, 0.0) is None
    assert MetricCalculator.calculate_roas(1000.0, -100.0) is None
    assert MetricCalculator.calculate_roas(-500.0, 100.0) is None
    assert MetricCalculator.calculate_roas(float("nan"), 100.0) is None


def test_enrich_record_valid() -> None:
    """Test enrich_record populates all derived metrics on NormalizedAdRecord."""
    record = NormalizedAdRecord(
        date="2026-09-01",
        platform=Platform.GOOGLE_ADS,
        campaign_name="Search_Brand",
        country="US",
        currency="USD",
        spend=500.0,
        impressions=10000,
        clicks=500,
        conversions=25.0,
        conversion_value=2000.0,
    )

    enriched = MetricCalculator.enrich_record(record)

    assert enriched is not record  # Returns a new instance
    assert enriched.date == record.date
    assert enriched.platform == record.platform
    assert enriched.campaign_name == record.campaign_name
    assert enriched.spend == record.spend

    assert enriched.ctr == 0.05
    assert enriched.cpc == 1.0
    assert enriched.cpm == 50.0
    assert enriched.cpa == 20.0
    assert enriched.roas == 4.0

    # Verify original record remains untouched (un-enriched)
    assert record.ctr is None
    assert record.cpc is None


def test_enrich_record_zero_denominators() -> None:
    """Test enrich_record sets metrics to None when raw denominators are 0."""
    record = NormalizedAdRecord(
        date="2026-09-01",
        platform=Platform.META_ADS,
        campaign_name="Retargeting",
        country="US",
        currency="USD",
        spend=0.0,
        impressions=0,
        clicks=0,
        conversions=0.0,
        conversion_value=0.0,
    )

    enriched = MetricCalculator.enrich_record(record)

    assert enriched.ctr is None
    assert enriched.cpc is None
    assert enriched.cpm is None
    assert enriched.cpa is None
    assert enriched.roas is None
