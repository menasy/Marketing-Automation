"""Unit tests for DetectAnomaliesUseCase and JSON export."""

import json
from pathlib import Path

from src.application.use_cases.detect_anomalies import DetectAnomaliesUseCase
from src.domain.enums.metric_type import MetricType
from src.domain.enums.platform import Platform
from src.domain.enums.severity import Severity
from src.domain.models.ad_record import NormalizedAdRecord
from src.domain.services.metric_calculator import MetricCalculator


def test_detect_anomalies_empty_records(tmp_path: Path) -> None:
    """Empty record list produces empty anomaly list and exports [] JSON."""
    json_path = tmp_path / "anomalies.json"
    use_case = DetectAnomaliesUseCase(output_path=str(json_path))

    anomalies = use_case.detect([])
    assert anomalies == []
    assert json_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8")) == []


def test_detect_anomalies_insufficient_baseline(tmp_path: Path) -> None:
    """Fewer than 7 historical baseline records yields no anomalies."""
    json_path = tmp_path / "anomalies.json"
    use_case = DetectAnomaliesUseCase(output_path=str(json_path))

    records: list[NormalizedAdRecord] = []
    for day in range(1, 6):  # Only 5 records
        raw = NormalizedAdRecord(
            date=f"2026-08-0{day}",
            platform=Platform.GOOGLE_ADS,
            campaign_name="Search_Campaign",
            country="US",
            currency="USD",
            spend=100.0,
            impressions=1000,
            clicks=50,
            conversions=10.0,
            conversion_value=200.0,
        )
        records.append(MetricCalculator.enrich_record(raw))

    anomalies = use_case.detect(records, window_days=14)
    assert anomalies == []


def test_detect_anomalies_successful_detection_and_json_export(
    tmp_path: Path,
) -> None:
    """Synthetic campaign with 14 baseline days and target date spike

    produces valid anomaly and JSON export.
    """
    json_path = tmp_path / "anomalies.json"
    use_case = DetectAnomaliesUseCase(output_path=str(json_path))

    records: list[NormalizedAdRecord] = []

    # 14 historical baseline days: spend = $200, conversions = 10 -> CPA = $20.0
    for day in range(1, 15):
        date_str = f"2026-08-{day:02d}"
        raw = NormalizedAdRecord(
            date=date_str,
            platform=Platform.GOOGLE_ADS,
            campaign_name="Search_Brand",
            country="US",
            currency="USD",
            spend=200.0,
            impressions=5000,
            clicks=250,
            conversions=10.0,
            conversion_value=400.0,
        )
        records.append(MetricCalculator.enrich_record(raw))

    # Target date 15: CPA spike -> spend = $500, conversions = 10 -> CPA = $50.0 (+150% spike!)
    target_raw = NormalizedAdRecord(
        date="2026-08-15",
        platform=Platform.GOOGLE_ADS,
        campaign_name="Search_Brand",
        country="US",
        currency="USD",
        spend=500.0,
        impressions=5000,
        clicks=250,
        conversions=10.0,
        conversion_value=400.0,
    )
    records.append(MetricCalculator.enrich_record(target_raw))

    anomalies = use_case.detect(records, window_days=14)

    assert len(anomalies) >= 1
    cpa_anomalies = [a for a in anomalies if a.metric == MetricType.CPA]
    assert len(cpa_anomalies) == 1
    cpa_anomaly = cpa_anomalies[0]

    assert cpa_anomaly.campaign_name == "Search_Brand"
    assert cpa_anomaly.platform == Platform.GOOGLE_ADS
    assert cpa_anomaly.country == "US"
    assert cpa_anomaly.current_value == 50.0
    assert cpa_anomaly.baseline_value == 20.0
    assert cpa_anomaly.change_rate == 1.50
    assert cpa_anomaly.severity == Severity.CRITICAL

    # Verify output JSON file export structure
    assert json_path.exists()
    exported_data = json.loads(json_path.read_text(encoding="utf-8"))
    assert isinstance(exported_data, list)
    assert len(exported_data) >= 1

    item = exported_data[0]
    required_keys = {
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
    assert required_keys.issubset(set(item.keys()))
    assert item["campaign"] == "Search_Brand"
    assert item["platform"] == "google_ads"
    assert item["country"] == "US"
    assert item["metric"] == "cpa"
    assert item["severity"] == "critical"
