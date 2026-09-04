import pytest

from src.domain.enums.platform import Platform
from src.domain.exceptions import NormalizationError
from src.domain.models.ad_record import NormalizedAdRecord
from src.infrastructure.data.normalization.google_normalizer import GoogleNormalizer


def test_normalize_valid_gaql_record() -> None:
    normalizer = GoogleNormalizer()
    raw_records: list[dict[str, object]] = [
        {
            "date": "2026-07-06",
            "campaign_name": "NK | Search | Brand",
            "country_code": "DE",
            "currency_code": "EUR",
            "impressions": 1000,
            "clicks": 100,
            "cost_micros": 50000000,  # 50.0 EUR
            "conversions": 10.0,
            "conversions_value": 200.0,
        }
    ]

    result = normalizer.normalize(raw_records)
    assert len(result) == 1
    record = result[0]

    assert isinstance(record, NormalizedAdRecord)
    assert record.date == "2026-07-06"
    assert record.platform == Platform.GOOGLE_ADS
    assert record.campaign_name == "NK | Search | Brand"
    assert record.country == "DE"
    assert record.currency == "EUR"
    assert record.spend == 50.0
    assert record.impressions == 1000
    assert record.clicks == 100
    assert record.conversions == 10.0
    assert record.conversion_value == 200.0

    # Derived metrics verification
    # CTR = 100 / 1000 = 0.1
    # CPC = 50.0 / 100 = 0.5
    # CPM = (50.0 / 1000) * 1000 = 50.0
    # CPA = 50.0 / 10.0 = 5.0
    # ROAS = 200.0 / 50.0 = 4.0
    assert record.ctr == pytest.approx(0.1)
    assert record.cpc == pytest.approx(0.5)
    assert record.cpm == pytest.approx(50.0)
    assert record.cpa == pytest.approx(5.0)
    assert record.roas == pytest.approx(4.0)


def test_normalize_valid_ui_record() -> None:
    normalizer = GoogleNormalizer()
    raw_records: list[dict[str, object]] = [
        {
            "Date": "07/06/2026",
            "Campaign Name": "AH | Shopping | UK",
            "Country": "UK",
            "Currency": "GBP",
            "Impressions": "500",
            "Clicks": "25",
            "Cost": "20.50",
            "Conversions": "2.5",
            "Conversion Value": "102.50",
        }
    ]

    result = normalizer.normalize(raw_records)
    assert len(result) == 1
    record = result[0]

    assert record.date == "2026-07-06"
    assert record.campaign_name == "AH | Shopping | UK"
    assert record.country == "UK"
    assert record.currency == "GBP"
    assert record.spend == 20.50
    assert record.impressions == 500
    assert record.clicks == 25
    assert record.conversions == 2.5
    assert record.conversion_value == 102.50


def test_normalize_negative_spend_clamped() -> None:
    normalizer = GoogleNormalizer()
    raw_records: list[dict[str, object]] = [
        {
            "date": "2026-07-06",
            "campaign_name": "Test Campaign",
            "cost_micros": -10000000,
            "Cost": -5.0,
            "impressions": 100,
            "clicks": 10,
        }
    ]

    result = normalizer.normalize(raw_records)
    assert len(result) == 1
    assert result[0].spend == 0.0


def test_normalize_zero_impressions_and_clicks_derived_metrics_none() -> None:
    normalizer = GoogleNormalizer()
    raw_records: list[dict[str, object]] = [
        {
            "date": "2026-07-06",
            "campaign_name": "Zero Metrics Campaign",
            "impressions": 0,
            "clicks": 0,
            "cost_micros": 0,
            "conversions": 0,
            "conversions_value": 0,
        }
    ]

    result = normalizer.normalize(raw_records)
    assert len(result) == 1
    record = result[0]

    assert record.ctr is None
    assert record.cpc is None
    assert record.cpm is None
    assert record.cpa is None
    assert record.roas is None


def test_normalize_date_formats() -> None:
    normalizer = GoogleNormalizer()
    date_samples = [
        ("2026-07-06", "2026-07-06"),
        ("2026/07/06", "2026-07-06"),
        ("07/06/2026", "2026-07-06"),
        ("20260706", "2026-07-06"),
        ("2026-07-06T00:00:00Z", "2026-07-06"),
    ]

    for raw_date, expected_iso in date_samples:
        raw_records: list[dict[str, object]] = [
            {"date": raw_date, "campaign_name": "Campaign", "impressions": 100, "clicks": 5}
        ]
        res = normalizer.normalize(raw_records)
        assert res[0].date == expected_iso, f"Expected {expected_iso} for raw date {raw_date}"


def test_normalize_unparseable_date_raises_error() -> None:
    normalizer = GoogleNormalizer()
    raw_records: list[dict[str, object]] = [
        {"date": "invalid-date-string", "campaign_name": "Campaign"}
    ]

    with pytest.raises(NormalizationError, match="unparseable date"):
        normalizer.normalize(raw_records)


def test_normalize_missing_or_nan_numerics() -> None:
    normalizer = GoogleNormalizer()
    raw_records: list[dict[str, object]] = [
        {
            "date": "2026-07-06",
            "campaign_name": "Missing Numerics",
            "impressions": None,
            "clicks": "N/A",
            "conversions": float("nan"),
            "conversions_value": float("inf"),
        }
    ]

    result = normalizer.normalize(raw_records)
    assert len(result) == 1
    record = result[0]

    assert record.impressions == 0
    assert record.clicks == 0
    assert record.conversions == 0.0
    assert record.conversion_value == 0.0
