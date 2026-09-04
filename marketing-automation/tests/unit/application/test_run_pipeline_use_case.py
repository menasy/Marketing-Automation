"""Unit tests for RunPipelineUseCase orchestrator."""

import uuid
from datetime import date
from unittest.mock import MagicMock

from src.application.dto.normalization_result import NormalizationResult
from src.application.dto.pipeline_request import PipelineRequest
from src.application.use_cases.run_pipeline import RunPipelineUseCase
from src.domain.enums.metric_type import MetricType
from src.domain.enums.operational import IssueType
from src.domain.enums.platform import Platform
from src.domain.enums.severity import Severity
from src.domain.models.ad_record import NormalizedAdRecord
from src.domain.models.anomaly import AnomalyItem
from src.domain.models.briefing import ExecutiveBriefing
from src.domain.models.operational_finding import OperationalFinding


def _create_sample_anomaly(severity: Severity = Severity.CRITICAL) -> AnomalyItem:
    return AnomalyItem(
        campaign_name="Search_Brand_US",
        platform=Platform.GOOGLE_ADS,
        country="US",
        metric=MetricType.CPA,
        current_value=150.0,
        baseline_value=50.0,
        change_rate=2.0,
        z_score=3.5,
        severity=severity,
        direction=MetricType.CPA.value,  # type: ignore[arg-type]
        detection_method="rolling_zscore",
        rationale="CPA spiked significantly",
    )


def test_run_pipeline_successful_execution_sequence() -> None:
    """Verify end-to-end execution sequence, UUID generation, timing, and result formatting."""
    mock_normalize = MagicMock()
    mock_normalize.execute.return_value = NormalizationResult(
        records=[
            NormalizedAdRecord(
                date="2026-09-01",
                platform=Platform.GOOGLE_ADS,
                campaign_name="Test",
                country="US",
                currency="USD",
                spend=100.0,
                impressions=1000,
                clicks=50,
                conversions=5.0,
                conversion_value=250.0,
            )
        ],
        total_raw_records_read=1,
        skipped_records_count=0,
        summary_by_platform={"google_ads": 1},
    )

    mock_baseline = MagicMock()
    mock_detect = MagicMock()
    anomaly_item = _create_sample_anomaly(Severity.CRITICAL)
    mock_detect.detect.return_value = [anomaly_item]

    mock_analyze = MagicMock()
    mock_analyze.execute.return_value = [
        OperationalFinding(
            campaign_name="Search_Brand_US",
            platform=Platform.GOOGLE_ADS,
            country="US",
            primary_metric=MetricType.CPA,
            severity=Severity.CRITICAL,
            issue_type=IssueType.PERFORMANCE,
            evidence_summary="CPA increased 200%",
            business_impact="High CPA burn",
            metric_change="CPA: $50 → $150 (+200%)",
            operational_action="Günlük bütçeyi %20 kısın, hedef CPA/ROAS teklifini güncelleyin.",
            budget_action="Reduce budget by 20%",
            bid_action="Lower bid",
            creative_action="Refresh creative",
            tracking_action="Verify tracking",
            score=95.0,
        )
    ]

    mock_briefing = MagicMock()
    mock_briefing.execute.return_value = ExecutiveBriefing(
        summary="Executive Briefing Summary",
        raw_markdown="# Executive Briefing",
    )

    orchestrator = RunPipelineUseCase(
        normalize_data_use_case=mock_normalize,
        build_baseline_use_case=mock_baseline,
        detect_anomalies_use_case=mock_detect,
        analyze_findings_use_case=mock_analyze,
        generate_briefing_use_case=mock_briefing,
    )

    request = PipelineRequest(
        google_csv_path="data/google_ads_daily.csv",
        meta_csv_path="data/meta_ads_daily.csv",
        window_days=14,
        reporting_currency="USD",
        target_date=date(2026, 9, 1),
    )

    result = orchestrator.execute(request)

    # 1. Verify stage call sequence
    mock_normalize.execute.assert_called_once()
    mock_baseline.execute.assert_called_once()
    mock_detect.detect.assert_called_once()
    mock_analyze.execute.assert_called_once()
    mock_briefing.execute.assert_called_once()

    # 2. Verify UUID4 execution ID
    parsed_uuid = uuid.UUID(result.execution_id)
    assert str(parsed_uuid) == result.execution_id

    # 3. Verify status, counts, timing
    assert result.status == "success"
    assert result.anomalies_count == 1
    assert result.critical_count == 1
    assert result.duration_seconds > 0.0
    assert result.stage_statuses["normalize_data"] == "success"
    assert result.stage_statuses["build_baseline"] == "success"
    assert result.stage_statuses["detect_anomalies"] == "success"
    assert result.stage_statuses["analyze_findings"] == "success"
    assert result.stage_statuses["generate_briefing"] == "success"


def test_run_pipeline_unique_uuid_per_execution() -> None:
    """Verify that every execution generates a distinct UUID4 id."""
    mock_normalize = MagicMock()
    mock_normalize.execute.return_value = NormalizationResult(
        records=[],
        total_raw_records_read=0,
        skipped_records_count=0,
        summary_by_platform={},
    )
    mock_detect = MagicMock()
    mock_detect.detect.return_value = []

    orchestrator = RunPipelineUseCase(
        normalize_data_use_case=mock_normalize,
        build_baseline_use_case=MagicMock(),
        detect_anomalies_use_case=mock_detect,
        analyze_findings_use_case=MagicMock(),
        generate_briefing_use_case=MagicMock(),
    )

    res1 = orchestrator.execute()
    res2 = orchestrator.execute()

    assert res1.execution_id != res2.execution_id
    assert isinstance(uuid.UUID(res1.execution_id), uuid.UUID)
    assert isinstance(uuid.UUID(res2.execution_id), uuid.UUID)


def test_run_pipeline_fault_tolerance_non_critical_stage_failure() -> None:
    """Verify LLM briefing failure falls back gracefully without losing previous stage outputs."""
    mock_normalize = MagicMock()
    mock_normalize.execute.return_value = NormalizationResult(
        records=[],
        total_raw_records_read=0,
        skipped_records_count=0,
        summary_by_platform={},
    )
    mock_detect = MagicMock()
    mock_detect.detect.return_value = [_create_sample_anomaly(Severity.CRITICAL)]

    mock_briefing = MagicMock()
    mock_briefing.execute.side_effect = RuntimeError("LLM API Provider Timeout")

    orchestrator = RunPipelineUseCase(
        normalize_data_use_case=mock_normalize,
        build_baseline_use_case=MagicMock(),
        detect_anomalies_use_case=mock_detect,
        analyze_findings_use_case=MagicMock(),
        generate_briefing_use_case=mock_briefing,
    )

    result = orchestrator.execute()

    assert result.status == "partial_success"
    assert result.stage_statuses["generate_briefing"] == "fallback"
    assert result.anomalies_count == 1
    assert result.critical_count == 1


def test_run_pipeline_critical_stage_failure() -> None:
    """Verify that a failure in a critical stage returns a failed result immediately."""
    mock_normalize = MagicMock()
    mock_normalize.execute.side_effect = ValueError("Corrupted CSV input")

    orchestrator = RunPipelineUseCase(
        normalize_data_use_case=mock_normalize,
        build_baseline_use_case=MagicMock(),
        detect_anomalies_use_case=MagicMock(),
        analyze_findings_use_case=MagicMock(),
        generate_briefing_use_case=MagicMock(),
    )

    result = orchestrator.execute()

    assert result.status == "failed"
    assert result.stage_statuses["normalize_data"] == "failed"
    assert result.anomalies_count == 0
    assert result.critical_count == 0
