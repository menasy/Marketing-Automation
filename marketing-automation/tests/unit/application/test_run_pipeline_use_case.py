"""Unit tests for RunPipelineUseCase orchestrator."""

import asyncio
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from src.agent.schemas.reasoning import (
    BatchAnalysisResult,
    DiagnosedFinding,
    Hypothesis,
    OperationalActionPlan,
)
from src.application.dto.normalization_result import NormalizationResult
from src.application.dto.pipeline_request import PipelineRequest
from src.application.use_cases.run_pipeline import RunPipelineUseCase
from src.domain.enums.metric_type import MetricType
from src.domain.enums.platform import Platform
from src.domain.enums.severity import Severity
from src.domain.models.ad_record import NormalizedAdRecord
from src.domain.models.anomaly import AnomalyItem


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


def _create_sample_batch_result() -> BatchAnalysisResult:
    return BatchAnalysisResult(
        findings=[
            DiagnosedFinding(
                campaign_name="Search_Brand_US",
                platform="google_ads",
                country="US",
                issue_type="DATA_QUALITY",
                confidence_score=0.95,
                root_cause_analysis="Conversion tracking breakdown",
                competing_hypotheses=[Hypothesis(statement="Tag missing", confidence=0.95)],
                selected_hypothesis=Hypothesis(statement="Tag missing", confidence=0.95),
                action_plan=OperationalActionPlan(
                    budget_action="HOLD_CURRENT_BUDGET",
                    bid_action="NO_CHANGE",
                    creative_action="NO_CHANGE",
                    tracking_action="VERIFY_TAG",
                    rationale="Check tracking",
                    concrete_steps=["Check GTM container"],
                    expected_effect="Restore tracking",
                    risk_level="LOW",
                    requires_approval=False,
                ),
                metric_change_summary="CPA: $50 → $150 (+200%)",
                business_impact_narrative="Data tracking breakdown",
            )
        ],
        executive_summary="Executive Briefing Summary",
        overall_data_health="HEALTHY",
        analysis_timestamp="2026-09-01T12:00:00Z",
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

    mock_batch_orchestrator = MagicMock()
    mock_batch_orchestrator.run = AsyncMock(return_value=_create_sample_batch_result())

    mock_artifact_service = MagicMock()
    mock_artifact_service.write_all.return_value = (
        "output/anomalies.json",
        "output/operational_assessment.md",
        "output/top_3_findings.md",
        "output/sample_briefing.md",
    )

    mock_slack = MagicMock()

    orchestrator = RunPipelineUseCase(
        normalize_data_use_case=mock_normalize,
        build_baseline_use_case=mock_baseline,
        detect_anomalies_use_case=mock_detect,
        batch_orchestrator=mock_batch_orchestrator,
        artifact_service=mock_artifact_service,
        notification_service=mock_slack,
    )

    request = PipelineRequest(
        google_csv_path="data/google_ads_daily.csv",
        meta_csv_path="data/meta_ads_daily.csv",
        window_days=14,
        reporting_currency="USD",
        target_date=date(2026, 9, 1),
    )

    result = asyncio.run(orchestrator.execute(request))

    # 1. Verify stage call sequence
    mock_normalize.execute.assert_called_once()
    mock_baseline.execute.assert_called_once()
    mock_detect.detect.assert_called_once()
    mock_batch_orchestrator.run.assert_awaited_once()

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
    assert result.stage_statuses["compile_dossier"] == "success"
    assert result.stage_statuses["agent_reasoning"] == "success"
    assert result.stage_statuses["write_artifacts"] == "success"


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

    mock_batch_orchestrator = MagicMock()
    mock_batch_orchestrator.run = AsyncMock(return_value=_create_sample_batch_result())

    orchestrator = RunPipelineUseCase(
        normalize_data_use_case=mock_normalize,
        build_baseline_use_case=MagicMock(),
        detect_anomalies_use_case=mock_detect,
        batch_orchestrator=mock_batch_orchestrator,
        artifact_service=MagicMock(),
        notification_service=MagicMock(),
    )

    res1 = asyncio.run(orchestrator.execute())
    res2 = asyncio.run(orchestrator.execute())

    assert res1.execution_id != res2.execution_id
    assert isinstance(uuid.UUID(res1.execution_id), uuid.UUID)
    assert isinstance(uuid.UUID(res2.execution_id), uuid.UUID)


def test_run_pipeline_fault_tolerance_non_critical_stage_failure() -> None:
    """Verify agent reasoning failure falls back gracefully without losing previous outputs."""
    mock_normalize = MagicMock()
    mock_normalize.execute.return_value = NormalizationResult(
        records=[],
        total_raw_records_read=0,
        skipped_records_count=0,
        summary_by_platform={},
    )
    mock_detect = MagicMock()
    mock_detect.detect.return_value = [_create_sample_anomaly(Severity.CRITICAL)]

    mock_batch_orchestrator = MagicMock()
    mock_batch_orchestrator.run = AsyncMock(side_effect=RuntimeError("LLM API Provider Timeout"))

    orchestrator = RunPipelineUseCase(
        normalize_data_use_case=mock_normalize,
        build_baseline_use_case=MagicMock(),
        detect_anomalies_use_case=mock_detect,
        batch_orchestrator=mock_batch_orchestrator,
        artifact_service=MagicMock(),
        notification_service=MagicMock(),
    )

    result = asyncio.run(orchestrator.execute())

    assert result.status == "partial_success"
    assert result.stage_statuses["agent_reasoning"] == "fallback"
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
        batch_orchestrator=MagicMock(),
        artifact_service=MagicMock(),
        notification_service=MagicMock(),
    )

    result = asyncio.run(orchestrator.execute())

    assert result.status == "failed"
    assert result.stage_statuses["normalize_data"] == "failed"
    assert result.anomalies_count == 0
    assert result.critical_count == 0
