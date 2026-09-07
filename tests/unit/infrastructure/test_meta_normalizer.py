import pytest

from src.domain.enums.platform import Platform
from src.domain.exceptions import NormalizationError
from src.domain.models.ad_record import NormalizedAdRecord
from src.infrastructure.data.normalization.meta_normalizer import MetaNormalizer


def test_normalize_valid_meta_csv_record() -> None:
    normalizer = MetaNormalizer()
    raw_records: list[dict[str, object]] = [
        {
            "date_start": "2026-07-06",
            "campaign_name": "NK | ABO | Prospecting EU",
            "country": "DE",
            "currency": "USD",
            "impressions": 50000,
            "inline_link_clicks": 500,
            "spend": 250.0,
            "actions_purchase": 10.0,
            "action_values_purchase": 1000.0,
        }
    ]

    result = normalizer.normalize(raw_records)
    assert len(result) == 1
    record = result[0]

    assert isinstance(record, NormalizedAdRecord)
    assert record.date == "2026-07-06"
    assert record.platform == Platform.META_ADS
    assert record.campaign_name == "NK | ABO | Prospecting EU"
    assert record.country == "DE"
    assert record.currency == "USD"
    assert record.spend == 250.0
    assert record.impressions == 50000
    assert record.clicks == 500
    assert record.conversions == 10.0
    assert record.conversion_value == 1000.0

    # Derived metrics verification
    # CTR = 500 / 50000 = 0.01
    # CPC = 250.0 / 500 = 0.5
    # CPM = (250.0 / 50000) * 1000 = 5.0
    # CPA = 250.0 / 10.0 = 25.0
    # ROAS = 1000.0 / 250.0 = 4.0
    assert record.ctr == pytest.approx(0.01)
    assert record.cpc == pytest.approx(0.5)
    assert record.cpm == pytest.approx(5.0)
    assert record.cpa == pytest.approx(25.0)
    assert record.roas == pytest.approx(4.0)


def test_normalize_structured_actions_list() -> None:
    normalizer = MetaNormalizer()
    raw_records: list[dict[str, object]] = [
        {
            "date_start": "2026-07-06",
            "campaign_name": "Meta Campaign Structured",
            "impressions": 10000,
            "clicks": 200,
            "amount_spent": 100.0,
            "actions": [
                {"action_type": "link_click", "value": "200"},
                {"action_type": "offsite_conversion.fb_pixel_purchase", "value": "5.0"},
            ],
            "action_values": [
                {"action_type": "offsite_conversion.fb_pixel_purchase", "value": "350.0"}
            ],
        }
    ]

    result = normalizer.normalize(raw_records)
    assert len(result) == 1
    record = result[0]

    assert record.spend == 100.0
    assert record.conversions == 5.0
    assert record.conversion_value == 350.0
    assert record.cpa == pytest.approx(20.0)
    assert record.roas == pytest.approx(3.5)


def test_normalize_structured_actions_json_string() -> None:
    normalizer = MetaNormalizer()
    raw_records: list[dict[str, object]] = [
        {
            "date_start": "2026-07-06",
            "campaign_name": "Meta Campaign JSON String",
            "impressions": 10000,
            "clicks": 100,
            "spend": 50.0,
            "actions": '[{"action_type": "purchase", "value": "4.0"}]',
            "action_values": '[{"action_type": "purchase", "value": "200.0"}]',
        }
    ]

    result = normalizer.normalize(raw_records)
    assert len(result) == 1
    record = result[0]

    assert record.conversions == 4.0
    assert record.conversion_value == 200.0


def test_normalize_structured_actions_dict() -> None:
    normalizer = MetaNormalizer()
    raw_records: list[dict[str, object]] = [
        {
            "date_start": "2026-07-06",
            "campaign_name": "Meta Campaign Dict",
            "impressions": 1000,
            "clicks": 20,
            "spend": 30.0,
            "actions": {"purchase": 3.0},
            "action_values": {"purchase": 150.0},
        }
    ]

    result = normalizer.normalize(raw_records)
    assert len(result) == 1
    record = result[0]

    assert record.conversions == 3.0
    assert record.conversion_value == 150.0


def test_normalize_negative_spend_clamped() -> None:
    normalizer = MetaNormalizer()
    raw_records: list[dict[str, object]] = [
        {
            "date_start": "2026-07-06",
            "campaign_name": "Negative Spend Meta",
            "spend": -50.0,
            "impressions": 100,
            "clicks": 10,
        }
    ]

    result = normalizer.normalize(raw_records)
    assert len(result) == 1
    assert result[0].spend == 0.0


def test_normalize_zero_impressions_and_clicks_derived_metrics_none() -> None:
    normalizer = MetaNormalizer()
    raw_records: list[dict[str, object]] = [
        {
            "date_start": "2026-07-06",
            "campaign_name": "Zero Metrics Meta",
            "impressions": 0,
            "clicks": 0,
            "spend": 0.0,
            "actions_purchase": 0,
            "action_values_purchase": 0,
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
    normalizer = MetaNormalizer()
    date_samples = [
        ("2026-07-06", "2026-07-06"),
        ("2026/07/06", "2026-07-06"),
        ("07/06/2026", "2026-07-06"),
        ("20260706", "2026-07-06"),
        ("2026-07-06T00:00:00Z", "2026-07-06"),
    ]

    for raw_date, expected_iso in date_samples:
        raw_records: list[dict[str, object]] = [
            {
                "date_start": raw_date,
                "campaign_name": "Campaign Meta",
                "impressions": 100,
                "clicks": 5,
            }
        ]
        res = normalizer.normalize(raw_records)
        assert res[0].date == expected_iso, f"Expected {expected_iso} for raw date {raw_date}"


def test_normalize_unparseable_date_raises_error() -> None:
    normalizer = MetaNormalizer()
    raw_records: list[dict[str, object]] = [
        {"date_start": "invalid-date-string", "campaign_name": "Campaign"}
    ]

    with pytest.raises(NormalizationError, match="unparseable date"):
        normalizer.normalize(raw_records)


def test_normalize_missing_or_nan_numerics() -> None:
    normalizer = MetaNormalizer()
    raw_records: list[dict[str, object]] = [
        {
            "date_start": "2026-07-06",
            "campaign_name": "Missing Numerics Meta",
            "impressions": None,
            "inline_link_clicks": "N/A",
            "actions_purchase": float("nan"),
            "action_values_purchase": float("inf"),
        }
    ]

    result = normalizer.normalize(raw_records)
    assert len(result) == 1
    record = result[0]

    assert record.impressions == 0
    assert record.clicks == 0
    assert record.conversions == 0.0
    assert record.conversion_value == 0.0
