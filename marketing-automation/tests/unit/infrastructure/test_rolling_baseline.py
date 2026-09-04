from datetime import date, timedelta

from src.domain.enums.metric_type import MetricType
from src.domain.enums.platform import Platform
from src.domain.models.ad_record import NormalizedAdRecord
from src.infrastructure.anomaly.rolling_baseline import RollingBaselineEngine


def _create_record(date_str: str, spend: float = 100.0, clicks: int = 10) -> NormalizedAdRecord:
    """Helper to generate synthetic NormalizedAdRecord."""
    return NormalizedAdRecord(
        date=date_str,
        platform=Platform.GOOGLE_ADS,
        campaign_name="Brand_Campaign",
        country="US",
        currency="USD",
        spend=spend,
        impressions=1000,
        clicks=clicks,
        conversions=2.0,
        conversion_value=200.0,
    )


def test_14_day_window_calculation() -> None:
    """Test exact 14-day rolling baseline calculation."""
    engine = RollingBaselineEngine()
    records: list[NormalizedAdRecord] = []

    # Generate 20 days of data from 2026-09-01 to 2026-09-20
    start_dt = date(2026, 9, 1)
    for i in range(20):
        dt_str = (start_dt + timedelta(days=i)).isoformat()
        records.append(_create_record(dt_str, spend=100.0 + i))

    target_date = "2026-09-15"
    baselines = engine.calculate_baselines(records, target_date, window_days=14)

    assert len(baselines) == 1
    b = baselines[0]
    assert b.window_start == date(2026, 9, 1)
    assert b.window_end == date(2026, 9, 14)
    assert b.insufficient_history is False

    spend_stats = b.metrics[MetricType.SPEND]
    assert spend_stats.sample_count == 14
    assert spend_stats.insufficient_history is False
    # spend values from Sep 1 to Sep 14: 100 to 113. Mean = 106.5
    assert spend_stats.mean == 106.5


def test_30_day_window_calculation() -> None:
    """Test exact 30-day rolling baseline calculation."""
    engine = RollingBaselineEngine()
    records: list[NormalizedAdRecord] = []

    start_dt = date(2026, 8, 1)
    for i in range(45):
        dt_str = (start_dt + timedelta(days=i)).isoformat()
        records.append(_create_record(dt_str, spend=150.0))

    target_date = "2026-09-10"
    baselines = engine.calculate_baselines(records, target_date, window_days=30)

    assert len(baselines) == 1
    b = baselines[0]
    assert b.window_start == date(2026, 8, 11)
    assert b.window_end == date(2026, 9, 9)

    spend_stats = b.metrics[MetricType.SPEND]
    assert spend_stats.sample_count == 30
    assert spend_stats.mean == 150.0


def test_look_ahead_bias_exclusion() -> None:
    """Test that target date D is strictly excluded from historical baseline."""
    engine = RollingBaselineEngine()
    records: list[NormalizedAdRecord] = []

    start_dt = date(2026, 9, 1)
    # 14 baseline days (Sep 1 to Sep 14) with spend = 100.0
    for i in range(14):
        dt_str = (start_dt + timedelta(days=i)).isoformat()
        records.append(_create_record(dt_str, spend=100.0))

    # Target date D (Sep 15) with massive outlier spend = 1,000,000.0
    records.append(_create_record("2026-09-15", spend=1000000.0))

    baselines, currents = engine.get_baseline_and_current(records, "2026-09-15", window_days=14)

    assert len(baselines) == 1
    b = baselines[0]
    assert b.metrics[MetricType.SPEND].mean == 100.0  # Baseline unaffected by day D
    assert b.metrics[MetricType.SPEND].std == 0.0

    assert len(currents) == 1
    c = currents[0]
    assert c.date == date(2026, 9, 15)
    assert c.metrics[MetricType.SPEND] == 1000000.0


def test_insufficient_history_guard() -> None:
    """Test that sample_count < 7 flags insufficient_history."""
    engine = RollingBaselineEngine()
    records: list[NormalizedAdRecord] = []

    # Provide only 5 records in historical window
    start_dt = date(2026, 9, 1)
    for i in range(5):
        dt_str = (start_dt + timedelta(days=i)).isoformat()
        records.append(_create_record(dt_str, spend=50.0))

    baselines = engine.calculate_baselines(records, "2026-09-15", window_days=14)

    assert len(baselines) == 1
    b = baselines[0]
    assert b.insufficient_history is True
    assert b.metrics[MetricType.SPEND].sample_count == 5
    assert b.metrics[MetricType.SPEND].insufficient_history is True


def test_zero_variance_scenario() -> None:
    """Test constant historical values produce std == 0.0 cleanly."""
    engine = RollingBaselineEngine()
    records: list[NormalizedAdRecord] = []

    start_dt = date(2026, 9, 1)
    for i in range(14):
        dt_str = (start_dt + timedelta(days=i)).isoformat()
        records.append(_create_record(dt_str, spend=75.0))

    baselines = engine.calculate_baselines(records, "2026-09-15", window_days=14)

    assert len(baselines) == 1
    b = baselines[0]
    assert b.metrics[MetricType.SPEND].mean == 75.0
    assert b.metrics[MetricType.SPEND].std == 0.0


def test_missing_dates_within_window() -> None:
    """Test missing intermediate dates inside window are handled without error."""
    engine = RollingBaselineEngine()
    records: list[NormalizedAdRecord] = []

    # Add records for days: 1, 3, 5, 7, 9, 11, 13, 14 (8 records out of 14 days)
    for day in [1, 3, 5, 7, 9, 11, 13, 14]:
        dt_str = date(2026, 9, day).isoformat()
        records.append(_create_record(dt_str, spend=100.0))

    baselines = engine.calculate_baselines(records, "2026-09-15", window_days=14)

    assert len(baselines) == 1
    b = baselines[0]
    assert b.metrics[MetricType.SPEND].sample_count == 8
    assert b.metrics[MetricType.SPEND].insufficient_history is False


def test_granularity_isolation_multiple_campaigns() -> None:
    """Test baselines are isolated per platform/campaign/country key."""
    engine = RollingBaselineEngine()
    records: list[NormalizedAdRecord] = []

    start_dt = date(2026, 9, 1)
    for i in range(14):
        dt_str = (start_dt + timedelta(days=i)).isoformat()
        # Campaign A: Google Ads - Brand_Campaign - US
        rec_a = NormalizedAdRecord(
            date=dt_str,
            platform=Platform.GOOGLE_ADS,
            campaign_name="Brand_Campaign",
            country="US",
            currency="USD",
            spend=100.0,
            impressions=1000,
            clicks=10,
            conversions=2.0,
            conversion_value=200.0,
        )
        # Campaign B: Meta Ads - Retargeting_Campaign - US
        rec_b = NormalizedAdRecord(
            date=dt_str,
            platform=Platform.META_ADS,
            campaign_name="Retargeting_Campaign",
            country="US",
            currency="USD",
            spend=500.0,
            impressions=5000,
            clicks=50,
            conversions=10.0,
            conversion_value=1000.0,
        )
        records.extend([rec_a, rec_b])

    baselines = engine.calculate_baselines(records, "2026-09-15", window_days=14)

    assert len(baselines) == 2
    campaign_names = {b.campaign_name for b in baselines}
    assert campaign_names == {"Brand_Campaign", "Retargeting_Campaign"}
