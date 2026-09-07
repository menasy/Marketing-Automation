import pytest

from src.domain.enums.platform import Platform
from src.domain.exceptions import NormalizationError
from src.domain.models.ad_record import NormalizedAdRecord
from src.infrastructure.data.normalization.currency_normalizer import (
    StaticCurrencyConverter,
)


def test_convert_same_currency_identity() -> None:
    converter = StaticCurrencyConverter()
    amount = 123.45

    assert converter.convert(amount, "USD", "USD") == amount
    assert converter.convert(amount, "eur", "EUR") == amount
    assert converter.convert(amount, "GBP", "gbp") == amount


def test_convert_precision_standard_currencies() -> None:
    converter = StaticCurrencyConverter()

    # 100 EUR to USD (1 EUR = 1.08 USD) -> 108.0 USD
    res_eur = converter.convert(100.0, "EUR", "USD")
    assert res_eur == pytest.approx(108.0)

    # 100 GBP to USD (1 GBP = 1.27 USD) -> 127.0 USD
    res_gbp = converter.convert(100.0, "GBP", "USD")
    assert res_gbp == pytest.approx(127.0)

    # 1000 TRY to USD (1 TRY = 0.029 USD) -> 29.0 USD
    res_try = converter.convert(1000.0, "TRY", "USD")
    assert res_try == pytest.approx(29.0)


def test_convert_cross_currency() -> None:
    converter = StaticCurrencyConverter()

    # 100 EUR to GBP -> 100 * (1.08 / 1.27) = 85.03937
    res = converter.convert(100.0, "EUR", "GBP")
    expected = 100.0 * (1.08 / 1.27)
    assert res == pytest.approx(expected)


def test_convert_unknown_currency_raises_error() -> None:
    converter = StaticCurrencyConverter()

    with pytest.raises(NormalizationError, match="Unsupported source currency"):
        converter.convert(100.0, "XYZ", "USD")

    with pytest.raises(NormalizationError, match="Unsupported target currency"):
        converter.convert(100.0, "USD", "ABC")


def test_convert_record_monetary_fields() -> None:
    converter = StaticCurrencyConverter()
    record = NormalizedAdRecord(
        date="2026-07-06",
        platform=Platform.GOOGLE_ADS,
        campaign_name="Test Campaign",
        country="DE",
        currency="EUR",
        spend=100.0,  # 100 EUR
        impressions=1000,
        clicks=100,
        conversions=10.0,
        conversion_value=500.0,  # 500 EUR
        ctr=0.1,
        cpc=1.0,
        cpm=100.0,
        cpa=10.0,
        roas=5.0,
    )

    converted = converter.convert_record(record, target_currency="USD")

    assert converted.currency == "USD"
    assert converted.spend == pytest.approx(108.0)
    assert converted.conversion_value == pytest.approx(540.0)

    # Recalculated metrics:
    # CPC = 108.0 / 100 = 1.08
    # CPM = (108.0 / 1000) * 1000 = 108.0
    # CPA = 108.0 / 10.0 = 10.8
    # ROAS = 540.0 / 108.0 = 5.0
    assert converted.cpc == pytest.approx(1.08)
    assert converted.cpm == pytest.approx(108.0)
    assert converted.cpa == pytest.approx(10.8)
    assert converted.roas == pytest.approx(5.0)


def test_convert_zero_and_invalid_amounts() -> None:
    converter = StaticCurrencyConverter()
    assert converter.convert(0.0, "EUR", "USD") == 0.0
    assert converter.convert(float("nan"), "EUR", "USD") == 0.0
    assert converter.convert(float("inf"), "EUR", "USD") == 0.0
