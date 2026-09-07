"""Unit tests for BatchReasoningOrchestrator self-correction reflection and fail-safe fallback."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent.exceptions import AgentExecutionError
from src.agent.runtime.context import AgentContext
from src.agent.runtime.gemini_client import IStructuredLLMClient
from src.agent.runtime.orchestrator import BatchReasoningOrchestrator
from src.agent.schemas.reasoning import (
    BatchAnalysisResult,
    DiagnosedFinding,
    Hypothesis,
    OperationalActionPlan,
)
from src.domain.models.data_quality_signal import DataQualitySignal, DataQualitySignalType
from src.domain.models.evidence_dossier import CampaignEvidence, EvidenceDossier, MetricEvidence


@pytest.fixture
def sample_dossier() -> EvidenceDossier:
    """Fixture providing a sample EvidenceDossier with active spend and DQ signal."""
    metric_conv = MetricEvidence(
        metric_name="conversions",
        current_value=0.0,
        baseline_value=50.0,
        delta_pct=-100.0,
        z_score=-4.0,
        is_anomaly=True,
    )
    metric_spend = MetricEvidence(
        metric_name="spend",
        current_value=1500.0,
        baseline_value=1500.0,
        delta_pct=0.0,
        z_score=0.0,
        is_anomaly=False,
    )
    dq_signal = DataQualitySignal(
        signal_type=DataQualitySignalType.ZERO_CONVERSIONS_WITH_ACTIVE_SPEND,
        is_triggered=True,
        metric_name="conversions",
        current_value=0.0,
        baseline_value=50.0,
        delta_pct=-100.0,
        factual_statement="Zero conversions with active spend $1500.0.",
    )
    campaign = CampaignEvidence(
        campaign_id="cmp-100",
        campaign_name="US_Search_Brand",
        platform="google_ads",
        account_id="acc-100",
        country="US",
        spend=1500.0,
        financial_impact_score=95.0,
        metrics={"conversions": metric_conv, "spend": metric_spend},
        data_quality_signals=(dq_signal,),
    )
    return EvidenceDossier(
        target_date="2026-09-07",
        baseline_window="14d",
        total_anomalies_detected=1,
        total_campaigns_impacted=1,
        top_campaign_evidence=(campaign,),
    )


@pytest.fixture
def prompt_file(tmp_path: Path) -> Path:
    """Fixture creating a temporary valid prompt template file."""
    file = tmp_path / "executive_briefing.md"
    file.write_text("System Prompt: You are a lead analyst.", encoding="utf-8")
    return file


@pytest.fixture
def valid_result() -> BatchAnalysisResult:
    """Fixture returning a valid BatchAnalysisResult."""
    hyp1 = Hypothesis(statement="Pixel issue", confidence=0.9)
    hyp2 = Hypothesis(statement="Creative fatigue", confidence=0.1)
    plan = OperationalActionPlan(
        budget_action="HOLD",
        bid_action="NO_CHANGE",
        creative_action="NO_ACTION",
        tracking_action="AUDIT",
        rationale="Audit pixel",
        concrete_steps=["Check GTM container"],
        expected_effect="Restore tracking",
        risk_level="LOW",
        requires_approval=False,
    )
    finding = DiagnosedFinding(
        campaign_name="US_Search_Brand",
        platform="google_ads",
        country="US",
        issue_type="DATA_QUALITY",
        confidence_score=0.9,
        root_cause_analysis="Conversions dropped by -100.0% with spend $1500",
        competing_hypotheses=[hyp1, hyp2],
        selected_hypothesis=hyp1,
        action_plan=plan,
        metric_change_summary="Conversions dropped by -100.0% with spend $1500",
        business_impact_narrative="Loss of conversion tracking",
    )
    return BatchAnalysisResult(
        findings=[finding],
        executive_summary="Executive summary briefing.",
        overall_data_health="DEGRADED",
        analysis_timestamp="2026-09-07T12:00:00Z",
    )


@pytest.fixture
def invalid_result() -> BatchAnalysisResult:
    """Fixture returning an invalid BatchAnalysisResult (hallucinated metric +300% CPA)."""
    hyp1 = Hypothesis(statement="Pixel issue", confidence=0.9)
    hyp2 = Hypothesis(statement="Creative fatigue", confidence=0.1)
    plan = OperationalActionPlan(
        budget_action="HOLD",
        bid_action="NO_CHANGE",
        creative_action="NO_ACTION",
        tracking_action="AUDIT",
        rationale="Audit pixel",
        concrete_steps=["Check GTM container"],
        expected_effect="Restore tracking",
        risk_level="LOW",
        requires_approval=False,
    )
    finding = DiagnosedFinding(
        campaign_name="US_Search_Brand",
        platform="google_ads",
        country="US",
        issue_type="DATA_QUALITY",
        confidence_score=0.9,
        root_cause_analysis="CPA spiked by +300% CPA",
        competing_hypotheses=[hyp1, hyp2],
        selected_hypothesis=hyp1,
        action_plan=plan,
        metric_change_summary="CPA increased by +300% CPA",
        business_impact_narrative="Loss of conversion tracking",
    )
    return BatchAnalysisResult(
        findings=[finding],
        executive_summary="Executive summary briefing.",
        overall_data_health="DEGRADED",
        analysis_timestamp="2026-09-07T12:00:00Z",
    )


@pytest.mark.asyncio
async def test_first_pass_verification_success(
    sample_dossier: EvidenceDossier, prompt_file: Path, valid_result: BatchAnalysisResult
) -> None:
    """Test Case 1: First-pass generation passes verification immediately."""
    mock_client = MagicMock(spec=IStructuredLLMClient)
    mock_client.generate_structured_analysis = AsyncMock(return_value=valid_result)

    orchestrator = BatchReasoningOrchestrator(client=mock_client, prompt_template_path=prompt_file)
    context = AgentContext(execution_id="exec-1", target_date="2026-09-07", dossier=sample_dossier)

    result = await orchestrator.run(context)

    assert result == valid_result
    assert context.result == valid_result
    assert mock_client.generate_structured_analysis.call_count == 1


@pytest.mark.asyncio
async def test_first_pass_fails_reflection_retry_succeeds(
    sample_dossier: EvidenceDossier,
    prompt_file: Path,
    invalid_result: BatchAnalysisResult,
    valid_result: BatchAnalysisResult,
) -> None:
    """Test Case 2: First-pass fails verification; reflection prompt sent; 2nd pass passes."""
    mock_client = MagicMock(spec=IStructuredLLMClient)
    mock_client.generate_structured_analysis = AsyncMock(side_effect=[invalid_result, valid_result])

    orchestrator = BatchReasoningOrchestrator(client=mock_client, prompt_template_path=prompt_file)
    context = AgentContext(execution_id="exec-2", target_date="2026-09-07", dossier=sample_dossier)

    result = await orchestrator.run(context)

    assert result == valid_result
    assert context.result == valid_result
    assert mock_client.generate_structured_analysis.call_count == 2

    _, kwargs = mock_client.generate_structured_analysis.call_args_list[1]
    assert "Your previous output failed deterministic verification" in kwargs["user_prompt"]
    assert "cited percentage 300.0%" in kwargs["user_prompt"]


@pytest.mark.asyncio
async def test_both_passes_fail_activates_fallback(
    sample_dossier: EvidenceDossier, prompt_file: Path, invalid_result: BatchAnalysisResult
) -> None:
    """Test Case 3: Both passes fail verification; DeterministicFallbackGenerator is invoked."""
    mock_client = MagicMock(spec=IStructuredLLMClient)
    mock_client.generate_structured_analysis = AsyncMock(
        side_effect=[invalid_result, invalid_result]
    )

    orchestrator = BatchReasoningOrchestrator(client=mock_client, prompt_template_path=prompt_file)
    context = AgentContext(execution_id="exec-3", target_date="2026-09-07", dossier=sample_dossier)

    result = await orchestrator.run(context)

    assert result is not None
    assert context.result == result
    assert mock_client.generate_structured_analysis.call_count == 2
    assert "[DETERMINISTIC FALLBACK - AGENT UNASSISTED]" in result.executive_summary
    assert result.findings[0].campaign_name == "US_Search_Brand"
    assert result.findings[0].issue_type == "DATA_QUALITY"
    assert result.findings[0].confidence_score == 1.0


@pytest.mark.asyncio
async def test_client_api_error_activates_fallback(
    sample_dossier: EvidenceDossier, prompt_file: Path
) -> None:
    """Test Case 4: Client throws error; system catches it and produces fallback output."""
    mock_client = MagicMock(spec=IStructuredLLMClient)
    mock_client.generate_structured_analysis = AsyncMock(
        side_effect=AgentExecutionError("HTTP 429 Rate limit / quota exhausted")
    )

    orchestrator = BatchReasoningOrchestrator(client=mock_client, prompt_template_path=prompt_file)
    context = AgentContext(execution_id="exec-4", target_date="2026-09-07", dossier=sample_dossier)

    result = await orchestrator.run(context)

    assert result is not None
    assert context.result == result
    assert "[DETERMINISTIC FALLBACK - AGENT UNASSISTED]" in result.executive_summary
    assert result.findings[0].campaign_name == "US_Search_Brand"
    assert result.overall_data_health == "CRITICAL"
