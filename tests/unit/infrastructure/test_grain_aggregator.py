import pytest

from src.domain.enums.platform import Platform
from src.domain.models.ad_record import NormalizedAdRecord
from src.infrastructure.data.normalization.grain_aggregator import GrainAggregator


def test_aggregate_empty_list() -> None:
    aggregator = GrainAggregator()
    assert aggregator.aggregate([]) == []


def test_aggregate_single_record_returns_as_is() -> None:
    aggregator = GrainAggregator()
    record = NormalizedAdRecord(
        date="2026-07-06",
        platform=Platform.GOOGLE_ADS,
        campaign_name="Single Campaign",
        country="DE",
        currency="EUR",
        spend=50.0,
        impressions=1000,
        clicks=50,
        conversions=5.0,
        conversion_value=200.0,
        ctr=0.05,
        cpc=1.0,
        cpm=50.0,
        cpa=10.0,
        roas=4.0,
    )

    res = aggregator.aggregate([record])
    assert len(res) == 1
    assert res[0] == record


def test_aggregate_multi_row_grouping_and_summation() -> None:
    aggregator = GrainAggregator()
    # Simulating Meta Ads split breakdown rows (e.g. website_pixel and conversions_api)
    row1 = NormalizedAdRecord(
        date="2026-07-06",
        platform=Platform.META_ADS,
        campaign_name="NK | ABO | Prospecting EU",
        country="DE",
        currency="USD",
        spend=100.0,
        impressions=5000,
        clicks=100,
        conversions=5.0,
        conversion_value=200.0,
    )
    row2 = NormalizedAdRecord(
        date="2026-07-06",
        platform=Platform.META_ADS,
        campaign_name="NK | ABO | Prospecting EU",
        country="DE",
        currency="USD",
        spend=100.0,
        impressions=5000,
        clicks=100,
        conversions=7.0,
        conversion_value=300.0,
    )

    res = aggregator.aggregate([row1, row2])

    assert len(res) == 1
    aggregated = res[0]

    assert aggregated.date == "2026-07-06"
    assert aggregated.platform == Platform.META_ADS
    assert aggregated.campaign_name == "NK | ABO | Prospecting EU"
    assert aggregated.country == "DE"
    assert aggregated.currency == "USD"

    # Volume sums:
    # Spend = 100 + 100 = 200.0
    # Impressions = 5000 + 5000 = 10000
    # Clicks = 100 + 100 = 200
    # Conversions = 5 + 7 = 12.0
    # Conversion Value = 200 + 300 = 500.0
    assert aggregated.spend == 200.0
    assert aggregated.impressions == 10000
    assert aggregated.clicks == 200
    assert aggregated.conversions == 12.0
    assert aggregated.conversion_value == 500.0

    # Recalculated derived metrics:
    # CTR = 200 / 10000 = 0.02
    # CPC = 200.0 / 200 = 1.0
    # CPM = (200.0 / 10000) * 1000 = 20.0
    # CPA = 200.0 / 12.0 = 16.6666...
    # ROAS = 500.0 / 200.0 = 2.5
    assert aggregated.ctr == pytest.approx(0.02)
    assert aggregated.cpc == pytest.approx(1.0)
    assert aggregated.cpm == pytest.approx(20.0)
    assert aggregated.cpa == pytest.approx(200.0 / 12.0)
    assert aggregated.roas == pytest.approx(2.5)


def test_aggregate_distinct_grain_keys_preserved() -> None:
    aggregator = GrainAggregator()
    row_de = NormalizedAdRecord(
        date="2026-07-06",
        platform=Platform.META_ADS,
        campaign_name="Prospecting",
        country="DE",
        currency="USD",
        spend=100.0,
        impressions=1000,
        clicks=50,
        conversions=2.0,
        conversion_value=100.0,
    )
    row_nl = NormalizedAdRecord(
        date="2026-07-06",
        platform=Platform.META_ADS,
        campaign_name="Prospecting",
        country="NL",
        currency="USD",
        spend=50.0,
        impressions=500,
        clicks=25,
        conversions=1.0,
        conversion_value=50.0,
    )
    row_date2 = NormalizedAdRecord(
        date="2026-07-07",
        platform=Platform.META_ADS,
        campaign_name="Prospecting",
        country="DE",
        currency="USD",
        spend=120.0,
        impressions=1200,
        clicks=60,
        conversions=3.0,
        conversion_value=150.0,
    )

    res = aggregator.aggregate([row_de, row_nl, row_date2])
    assert len(res) == 3
