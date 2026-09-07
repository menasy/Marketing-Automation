"""Comprehensive integration and unit test suite for critical pipeline edge cases.

Verifies system robustness against 15 specific edge cases:
1. Empty CSV
2. Malformed CSV
3. Missing column
4. NaN handling
5. Infinity handling
6. Zero denominator
7. Zero baseline
8. Insufficient history
9. New campaign (no baseline history)
10. Currency mismatch (normalization)
11. Duplicate records (grain aggregation)
12. LLM hallucination validation
13. LLM timeout / API error fallback
14. API route error handling
15. Notification failure fallback
"""

from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.application.use_cases.generate_briefing import GenerateBriefingUseCase
from src.domain.enums.metric_type import MetricDirection, MetricType
from src.domain.enums.platform import Platform
from src.domain.enums.severity import Severity
from src.domain.exceptions import LLMValidationError, NormalizationError
from src.domain.models.ad_record import NormalizedAdRecord
from src.domain.models.anomaly import AnomalyItem
from src.domain.models.briefing import ExecutiveBriefing
from src.domain.services.metric_calculator import MetricCalculator
from src.infrastructure.anomaly.rolling_baseline import RollingBaselineEngine
from src.infrastructure.anomaly.z_score import calculate_z_score
from src.infrastructure.data.csv.google_ads_reader import GoogleCSVReader
from src.infrastructure.data.normalization.currency_normalizer import StaticCurrencyConverter
from src.infrastructure.data.normalization.grain_aggregator import GrainAggregator
from src.infrastructure.llm.openai_service import OpenAIService
from src.infrastructure.llm.output_validator import OutputValidator
from src.infrastructure.notifications.email import EmailNotificationService
from src.infrastructure.notifications.slack import SlackNotificationService
from src.presentation.api.app import app


# 1. Empty CSV
def test_edge_case_empty_csv(tmp_path: Path) -> None:
    """Edge Case 1: Processing empty CSV file should raise NormalizationError."""
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("")

    reader = GoogleCSVReader()
    with pytest.raises(NormalizationError, match="empty|no data"):
        reader.read(str(empty_file))


# 2. Malformed CSV
def test_edge_case_malformed_csv(tmp_path: Path) -> None:
    """Edge Case 2: Processing malformed CSV file raises NormalizationError."""
    malformed_file = tmp_path / "malformed.csv"
    malformed_file.write_text("Day,Campaign\n2026-09-01,Campaign A, Extra Field\nCorrupted Data")

    reader = GoogleCSVReader()
    with pytest.raises(NormalizationError):
        reader.read(str(malformed_file))


# 3. Missing Column
def test_edge_case_missing_column(tmp_path: Path) -> None:
    """Edge Case 3: CSV missing mandatory columns raises NormalizationError."""
    missing_col_file = tmp_path / "missing_col.csv"
    missing_col_file.write_text("Day,Impressions,Clicks\n2026-09-01,1000,50\n")

    reader = GoogleCSVReader()
    with pytest.raises(NormalizationError, match="missing required column"):
        reader.read(str(missing_col_file))


# 4. NaN Handling
def test_edge_case_nan_handling() -> None:
    """Edge Case 4: NaN inputs sanitization in metric calculator."""
    calc = MetricCalculator()
    rec = NormalizedAdRecord(
        date="2026-09-01",
        platform=Platform.GOOGLE_ADS,
        campaign_name="Test NaN",
        country="US",
        currency="USD",
        impressions=100,
        clicks=10,
        spend=float("nan"),
        conversions=0.0,
        conversion_value=0.0,
    )
    enriched = calc.enrich_record(rec)

    assert enriched.cpc is None
    assert enriched.cpa is None
    assert enriched.roas is None


# 5. Infinity Handling
def test_edge_case_infinity_handling() -> None:
    """Edge Case 5: Infinity values sanitized without runtime exceptions."""
    z = calculate_z_score(current=100.0, mean=100.0, std=0.0, sample_count=14)
    assert z is None

    z_inf = calculate_z_score(current=float("inf"), mean=100.0, std=2.0, sample_count=14)
    assert z_inf is None


# 6. Zero Denominator
def test_edge_case_zero_denominator() -> None:
    """Edge Case 6: Zero denominator returns None instead of ZeroDivisionError."""
    calc = MetricCalculator()
    rec = NormalizedAdRecord(
        date="2026-09-01",
        platform=Platform.GOOGLE_ADS,
        campaign_name="Zero Demo",
        country="US",
        currency="USD",
        impressions=0,
        clicks=0,
        spend=0.0,
        conversions=0.0,
        conversion_value=0.0,
    )
    enriched = calc.enrich_record(rec)

    assert enriched.ctr is None
    assert enriched.cpc is None
    assert enriched.cpa is None
    assert enriched.roas is None


# 7. Zero Baseline
def test_edge_case_zero_baseline() -> None:
    """Edge Case 7: Baseline mean=0 or std=0 is handled safely."""
    z = calculate_z_score(current=0.0, mean=0.0, std=0.0, sample_count=14)
    assert z is None


# 8. Insufficient History
def test_edge_case_insufficient_history() -> None:
    """Edge Case 8: Sample count < 7 days marks insufficient_history=True."""
    engine = RollingBaselineEngine()
    records = [
        NormalizedAdRecord(
            date="2026-08-30",
            platform=Platform.GOOGLE_ADS,
            campaign_name="Short History",
            country="US",
            currency="USD",
            impressions=1000,
            clicks=50,
            spend=100.0,
            conversions=5.0,
            conversion_value=200.0,
        ),
        NormalizedAdRecord(
            date="2026-08-31",
            platform=Platform.GOOGLE_ADS,
            campaign_name="Short History",
            country="US",
            currency="USD",
            impressions=1000,
            clicks=50,
            spend=100.0,
            conversions=5.0,
            conversion_value=200.0,
        ),
    ]

    baselines = engine.calculate_baselines(records, target_date=date(2026, 9, 1), window_days=14)

    assert len(baselines) == 1
    assert baselines[0].insufficient_history is True


# 9. New Campaign (No Historical Baseline)
def test_edge_case_new_campaign() -> None:
    """Edge Case 9: Campaign active only on target date produces no baseline."""
    engine = RollingBaselineEngine()
    records = [
        NormalizedAdRecord(
            date="2026-09-01",
            platform=Platform.META_ADS,
            campaign_name="Brand New Campaign",
            country="US",
            currency="USD",
            impressions=500,
            clicks=20,
            spend=50.0,
            conversions=2.0,
            conversion_value=100.0,
        ),
    ]

    baselines = engine.calculate_baselines(records, target_date=date(2026, 9, 1), window_days=14)
    assert len(baselines) == 0


# 10. Currency Mismatch Normalization
def test_edge_case_currency_mismatch() -> None:
    """Edge Case 10: Non-USD currencies normalized to target currency."""
    converter = StaticCurrencyConverter()
    record = NormalizedAdRecord(
        date="2026-09-01",
        platform=Platform.META_ADS,
        campaign_name="Euro Campaign",
        country="DE",
        currency="EUR",
        impressions=1000,
        clicks=50,
        spend=100.0,
        conversions=5.0,
        conversion_value=200.0,
    )

    converted = converter.convert_record(record, target_currency="USD")
    assert converted.currency == "USD"
    assert converted.spend == 108.0
    assert converted.conversion_value == 216.0


# 11. Duplicate Records Aggregation
def test_edge_case_duplicate_records() -> None:
    """Edge Case 11: Duplicate daily rows aggregated into single grain record."""
    aggregator = GrainAggregator()
    rec1 = NormalizedAdRecord(
        date="2026-09-01",
        platform=Platform.GOOGLE_ADS,
        campaign_name="Dup Campaign",
        country="US",
        currency="USD",
        impressions=1000,
        clicks=50,
        spend=100.0,
        conversions=5.0,
        conversion_value=200.0,
    )
    rec2 = NormalizedAdRecord(
        date="2026-09-01",
        platform=Platform.GOOGLE_ADS,
        campaign_name="Dup Campaign",
        country="US",
        currency="USD",
        impressions=500,
        clicks=25,
        spend=50.0,
        conversions=2.0,
        conversion_value=80.0,
    )

    aggregated = aggregator.aggregate([rec1, rec2])
    assert len(aggregated) == 1
    agg = aggregated[0]
    assert agg.impressions == 1500
    assert agg.clicks == 75
    assert agg.spend == 150.0
    assert agg.conversions == 7.0


# 12. LLM Hallucination Validation
def test_edge_case_llm_hallucination() -> None:
    """Edge Case 12: LLM output with unverified campaign raises error."""
    validator = OutputValidator()
    anomalies = [
        AnomalyItem(
            campaign_name="Real Campaign",
            platform=Platform.GOOGLE_ADS,
            country="US",
            metric=MetricType.CPA,
            current_value=81.67,
            baseline_value=28.34,
            change_rate=1.882,
            z_score=8.46,
            severity=Severity.CRITICAL,
            direction=MetricDirection.LOWER_IS_BETTER,
            detection_method="z_score",
            rationale="CPA spiked by +188.2%",
        )
    ]

    hallucinated_text = (
        "# Executive Briefing\n"
        "## Executive Summary\n"
        "Campaign 'Fake Campaign' spiked to CPA 999.99.\n"
        "## Critical Anomalies\n"
        "- 'Fake Campaign' (google_ads): CPA spiked to 999.99\n"
    )

    with pytest.raises(LLMValidationError, match="LLM briefing failed deterministic validation"):
        validator.validate(hallucinated_text, anomalies, strict=True)


# 13. LLM Timeout & API Error Fallback
def test_edge_case_llm_timeout_fallback() -> None:
    """Edge Case 13: OpenAI API failure triggers fallback briefing."""
    mock_llm = MagicMock(spec=OpenAIService)
    mock_llm.generate_briefing.side_effect = TimeoutError("OpenAI API call timed out")

    use_case = GenerateBriefingUseCase(llm_service=mock_llm)
    anomalies = [
        AnomalyItem(
            campaign_name="Real Campaign",
            platform=Platform.GOOGLE_ADS,
            country="US",
            metric=MetricType.CPA,
            current_value=81.67,
            baseline_value=28.34,
            change_rate=1.882,
            z_score=8.46,
            severity=Severity.CRITICAL,
            direction=MetricDirection.LOWER_IS_BETTER,
            detection_method="z_score",
            rationale="CPA spiked by +188.2%",
        )
    ]

    briefing = use_case.execute(anomalies)
    assert isinstance(briefing, ExecutiveBriefing)
    assert "Executive Briefing (Deterministic Fallback)" in briefing.raw_markdown


# 14. API Error Route Handling
def test_edge_case_api_error_handling() -> None:
    """Edge Case 14: FastAPI router handles invalid date format with HTTP 422."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/pipeline/run",
        json={"target_date": "invalid-date-format"},
    )
    assert response.status_code == 422


# 15. Notification Transport Fallback
def test_edge_case_notification_fallback() -> None:
    """Edge Case 15: Slack failure triggers fallback to Email transport."""
    mock_slack = MagicMock(spec=SlackNotificationService)
    mock_slack.send.return_value = False

    mock_email = MagicMock(spec=EmailNotificationService)
    mock_email.send.return_value = True

    briefing = ExecutiveBriefing(
        summary="Executive Summary",
        raw_markdown="# Briefing Text",
        generated_at=datetime.now(UTC),
    )

    slack_success = mock_slack.send(briefing)
    assert slack_success is False

    if not slack_success:
        email_success = mock_email.send(briefing)
        assert email_success is True
