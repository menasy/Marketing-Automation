"""Integration tests for end-to-end anomaly detection pipeline."""

import json
from pathlib import Path

from src.application.use_cases.detect_anomalies import DetectAnomaliesUseCase
from src.application.use_cases.normalize_data import (
    DataSourceConfig,
    NormalizeDataUseCase,
)
from src.infrastructure.data.csv.google_ads_reader import GoogleCSVReader
from src.infrastructure.data.csv.meta_ads_reader import MetaCSVReader
from src.infrastructure.data.normalization.currency_normalizer import (
    StaticCurrencyConverter,
)
from src.infrastructure.data.normalization.google_normalizer import (
    GoogleNormalizer,
)
from src.infrastructure.data.normalization.grain_aggregator import (
    GrainAggregator,
)
from src.infrastructure.data.normalization.meta_normalizer import (
    MetaNormalizer,
)


def test_end_to_end_anomaly_pipeline_with_real_files(tmp_path: Path) -> None:
    """Execute Faz 2 normalization, Faz 4 anomaly detection, and assert output/anomalies.json."""
    google_csv = "data/google_ads_daily.csv"
    meta_csv = "data/meta_ads_daily.csv"

    assert Path(google_csv).exists(), f"Sample dataset {google_csv} must exist"
    assert Path(meta_csv).exists(), f"Sample dataset {meta_csv} must exist"

    # Step 1: Normalize CSV data (Faz 2)
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

    normalize_use_case = NormalizeDataUseCase(
        currency_provider=StaticCurrencyConverter(),
        grain_aggregator=GrainAggregator(),
        target_currency="USD",
    )
    normalization_result = normalize_use_case.execute([google_config, meta_config])

    assert len(normalization_result.records) > 0

    # Step 2: Detect anomalies and write JSON export (Faz 4)
    out_json = tmp_path / "anomalies.json"
    detect_use_case = DetectAnomaliesUseCase(output_path=str(out_json))

    detect_use_case.detect(records=normalization_result.records, window_days=14)

    # Step 3: Assert output JSON export structure
    assert out_json.exists(), f"Output JSON file {out_json} must be created"
    content = out_json.read_text(encoding="utf-8")
    parsed = json.loads(content)
    assert isinstance(parsed, list)

    required_schema_keys = {
        "campaign",
        "platform",
        "country",
        "metric",
        "current_value",
        "baseline_value",
        "change_rate",
        "z_score",
        "severity",
        "direction",
        "detection_method",
        "rationale",
    }

    for item in parsed:
        assert isinstance(item, dict)
        assert required_schema_keys.issubset(set(item.keys()))
        assert isinstance(item["campaign"], str)
        assert isinstance(item["platform"], str)
        assert isinstance(item["country"], str)
        assert isinstance(item["metric"], str)
        assert isinstance(item["current_value"], (int, float))
        assert isinstance(item["baseline_value"], (int, float))
        assert isinstance(item["change_rate"], (int, float))
        assert isinstance(item["z_score"], (int, float))
        assert item["severity"] in {"low", "medium", "high", "critical"}
        assert item["direction"] in {
            "higher_is_better",
            "lower_is_better",
            "neutral",
        }
        assert item["detection_method"] == "rolling_zscore"
        assert len(item["rationale"]) > 0

    # Also verify that when default path is used, output/anomalies.json is written
    default_detect_use_case = DetectAnomaliesUseCase()
    default_detect_use_case.detect(records=normalization_result.records, window_days=14)
    assert Path("output/anomalies.json").exists()
