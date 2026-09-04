from datetime import date

import pytest

from src.application.dto.baseline_dto import BaselineDatasetDTO
from src.application.ports.baseline_provider import IBaselineProvider
from src.application.use_cases.build_baseline import BuildBaselineUseCase
from src.domain.enums.metric_type import MetricType
from src.domain.enums.platform import Platform
from src.domain.models.ad_record import NormalizedAdRecord
from src.domain.models.metric import BaselineMetric, CurrentMetric, MetricStats


class MockBaselineProvider(IBaselineProvider):
    """Mock baseline provider for testing use case orchestration."""

    def __init__(
        self,
        baselines: list[BaselineMetric] | None = None,
        currents: list[CurrentMetric] | None = None,
    ) -> None:
        self._baselines = baselines or []
        self._currents = currents or []
        self.last_target_date: date | str | None = None
        self.last_window_days: int | None = None

    def calculate_baselines(
        self,
        records: list[NormalizedAdRecord],
        target_date: date | str,
        window_days: int = 14,
    ) -> list[BaselineMetric]:
        return self._baselines

    def extract_current_metrics(
        self,
        records: list[NormalizedAdRecord],
        target_date: date | str,
    ) -> list[CurrentMetric]:
        return self._currents

    def get_baseline_and_current(
        self,
        records: list[NormalizedAdRecord],
        target_date: date | str,
        window_days: int = 14,
    ) -> tuple[list[BaselineMetric], list[CurrentMetric]]:
        self.last_target_date = target_date
        self.last_window_days = window_days
        return self._baselines, self._currents


def _create_record(date_str: str) -> NormalizedAdRecord:
    return NormalizedAdRecord(
        date=date_str,
        platform=Platform.GOOGLE_ADS,
        campaign_name="Brand_Campaign",
        country="US",
        currency="USD",
        spend=100.0,
        impressions=1000,
        clicks=50,
        conversions=5.0,
        conversion_value=500.0,
    )


def test_auto_date_resolution() -> None:
    """Test that max(record.date) is automatically resolved when target_date is None."""
    records = [
        _create_record("2026-09-01"),
        _create_record("2026-09-10"),
        _create_record("2026-09-15"),
    ]
    provider = MockBaselineProvider()
    use_case = BuildBaselineUseCase(provider)

    dto = use_case.execute(records=records, target_date=None, window_days=14)

    assert dto.target_date == date(2026, 9, 15)
    assert provider.last_target_date == date(2026, 9, 15)
    assert provider.last_window_days == 14


def test_explicit_target_date_parsing() -> None:
    """Test explicit target_date parameter parsing."""
    records = [_create_record("2026-09-01"), _create_record("2026-09-15")]
    provider = MockBaselineProvider()
    use_case = BuildBaselineUseCase(provider)

    dto = use_case.execute(records=records, target_date="2026-09-05")

    assert dto.target_date == date(2026, 9, 5)
    assert provider.last_target_date == date(2026, 9, 5)


def test_explicit_date_object() -> None:
    """Test target_date passed as a datetime.date object."""
    records = [_create_record("2026-09-01")]
    provider = MockBaselineProvider()
    use_case = BuildBaselineUseCase(provider)

    dto = use_case.execute(records=records, target_date=date(2026, 9, 1))
    assert dto.target_date == date(2026, 9, 1)


def test_empty_records_auto_date_error() -> None:
    """Test error raised when resolving date from empty records."""
    provider = MockBaselineProvider()
    use_case = BuildBaselineUseCase(provider)

    with pytest.raises(ValueError, match="Cannot resolve target date"):
        use_case.execute(records=[], target_date=None)


def test_minimum_volume_guard_tagging() -> None:
    """Test tagging of low volume campaigns (spend <= 0 or impressions <= 0)."""
    normal_current = CurrentMetric(
        platform=Platform.GOOGLE_ADS,
        campaign_name="Normal_Campaign",
        country="US",
        date=date(2026, 9, 15),
        metrics={MetricType.SPEND: 100.0, MetricType.IMPRESSIONS: 1000.0},
    )
    low_spend_current = CurrentMetric(
        platform=Platform.GOOGLE_ADS,
        campaign_name="Zero_Spend_Campaign",
        country="US",
        date=date(2026, 9, 15),
        metrics={MetricType.SPEND: 0.0, MetricType.IMPRESSIONS: 500.0},
    )
    low_impr_current = CurrentMetric(
        platform=Platform.META_ADS,
        campaign_name="Zero_Impr_Campaign",
        country="US",
        date=date(2026, 9, 15),
        metrics={MetricType.SPEND: 50.0, MetricType.IMPRESSIONS: 0.0},
    )

    provider = MockBaselineProvider(currents=[normal_current, low_spend_current, low_impr_current])
    use_case = BuildBaselineUseCase(provider)

    records = [_create_record("2026-09-15")]
    dto: BaselineDatasetDTO = use_case.execute(records=records, target_date="2026-09-15")

    assert dto.total_campaigns_analyzed == 3
    assert dto.low_volume_campaigns_count == 2

    c_map = {c.campaign_name: c for c in dto.current_metrics}
    assert c_map["Normal_Campaign"].is_low_volume is False
    assert c_map["Zero_Spend_Campaign"].is_low_volume is True
    assert c_map["Zero_Impr_Campaign"].is_low_volume is True


def test_excluded_new_campaigns_count() -> None:
    """Test counting of excluded new campaigns with insufficient history."""
    stats = MetricStats(
        mean=10.0,
        std=1.0,
        median=10.0,
        sample_count=5,
        min_value=5.0,
        max_value=15.0,
        insufficient_history=True,
    )
    b_new = BaselineMetric(
        platform=Platform.GOOGLE_ADS,
        campaign_name="New_Campaign",
        country="US",
        window_start=date(2026, 9, 1),
        window_end=date(2026, 9, 14),
        metrics={MetricType.SPEND: stats},
        insufficient_history=True,
    )
    stats_normal = MetricStats(
        mean=100.0,
        std=10.0,
        median=100.0,
        sample_count=14,
        min_value=80.0,
        max_value=120.0,
        insufficient_history=False,
    )
    b_normal = BaselineMetric(
        platform=Platform.GOOGLE_ADS,
        campaign_name="Established_Campaign",
        country="US",
        window_start=date(2026, 9, 1),
        window_end=date(2026, 9, 14),
        metrics={MetricType.SPEND: stats_normal},
        insufficient_history=False,
    )

    provider = MockBaselineProvider(baselines=[b_new, b_normal])
    use_case = BuildBaselineUseCase(provider)

    records = [_create_record("2026-09-15")]
    dto = use_case.execute(records=records, target_date="2026-09-15")

    assert dto.excluded_new_campaigns_count == 1
    assert len(dto.baseline_metrics) == 2
    key_new = (Platform.GOOGLE_ADS, "New_Campaign", "US")
    assert dto.baseline_metrics[key_new].insufficient_history is True
