from pathlib import Path

from src.application.dto.normalization_result import NormalizationResult
from src.application.use_cases.normalize_data import (
    DataSourceConfig,
    NormalizeDataUseCase,
)
from src.domain.enums.platform import Platform
from src.infrastructure.data.csv.google_ads_reader import GoogleCSVReader
from src.infrastructure.data.csv.meta_ads_reader import MetaCSVReader
from src.infrastructure.data.normalization.currency_normalizer import (
    StaticCurrencyConverter,
)
from src.infrastructure.data.normalization.google_normalizer import GoogleNormalizer
from src.infrastructure.data.normalization.grain_aggregator import GrainAggregator
from src.infrastructure.data.normalization.meta_normalizer import MetaNormalizer


def test_end_to_end_normalization_pipeline_with_real_files() -> None:
    google_csv = "data/google_ads_daily.csv"
    meta_csv = "data/meta_ads_daily.csv"

    assert Path(google_csv).exists(), f"Sample data {google_csv} must exist"
    assert Path(meta_csv).exists(), f"Sample data {meta_csv} must exist"

    # Configure data sources
    google_config = DataSourceConfig(
        file_path=google_csv,
        reader=GoogleCSVReader(),
        normalizer=GoogleNormalizer(),
    )
    meta_config = DataSourceConfig(
        file_path=meta_csv,
        reader=MetaCSVReader(),
        normalizer=MetaNormalizer(),
    )

    # Initialize Use Case with ports
    use_case = NormalizeDataUseCase(
        currency_provider=StaticCurrencyConverter(),
        grain_aggregator=GrainAggregator(),
        target_currency="USD",
    )

    result: NormalizationResult = use_case.execute([google_config, meta_config])

    # Assertions on NormalizationResult structure
    assert isinstance(result, NormalizationResult)
    assert result.total_raw_records_read > 0
    assert len(result.records) > 0
    assert "google_ads" in result.summary_by_platform
    assert "meta_ads" in result.summary_by_platform
    assert result.summary_by_platform["google_ads"] > 0
    assert result.summary_by_platform["meta_ads"] > 0

    # Total records in summary must equal total records list length
    assert sum(result.summary_by_platform.values()) == len(result.records)

    # Verify canonical grain uniqueness (1 row = 1 platform x 1 campaign x 1 country x 1 date)
    seen_keys: set[tuple[Platform, str, str, str]] = set()
    for rec in result.records:
        key = (rec.platform, rec.campaign_name, rec.country, rec.date)
        assert key not in seen_keys, f"Duplicate grain row found for key: {key}"
        seen_keys.add(key)

        # Verify target currency
        assert rec.currency == "USD"

        # Verify no NaN or Inf in numeric fields
        assert not (rec.spend != rec.spend)  # NaN check
        assert not (rec.conversion_value != rec.conversion_value)

    # Verify deterministic sorting
    for i in range(len(result.records) - 1):
        r1 = result.records[i]
        r2 = result.records[i + 1]
        key1 = (r1.date, r1.platform.value, r1.campaign_name, r1.country)
        key2 = (r2.date, r2.platform.value, r2.campaign_name, r2.country)
        assert key1 <= key2, f"Records not sorted deterministically: {key1} > {key2}"


def test_normalization_pipeline_custom_target_currency(tmp_path: Path) -> None:
    # Synthetic mock CSV with EUR values
    csv_file = tmp_path / "eur_data.csv"
    csv_content = (
        "date,campaign_name,country_code,currency_code,impressions,clicks,cost_micros,conversions,conversions_value\n"
        "2026-07-06,Campaign EUR,DE,EUR,1000,100,50000000,10.0,200.0\n"
    )
    csv_file.write_text(csv_content, encoding="utf-8")

    source_config = DataSourceConfig(
        file_path=str(csv_file),
        reader=GoogleCSVReader(),
        normalizer=GoogleNormalizer(),
    )

    use_case = NormalizeDataUseCase(
        currency_provider=StaticCurrencyConverter(),
        target_currency="USD",  # Converts EUR (rate 1.08) to USD
    )

    result = use_case.execute([source_config])
    assert len(result.records) == 1
    rec = result.records[0]

    assert rec.currency == "USD"
    assert rec.spend == 54.0  # 50.0 EUR * 1.08 = 54.0 USD
    assert rec.conversion_value == 216.0  # 200.0 EUR * 1.08 = 216.0 USD
