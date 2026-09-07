"""Unit tests for BatchReasoningOrchestrator coordination flow and dossier serialization."""

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
def mock_llm_client() -> MagicMock:
    """Fixture returning a mocked IStructuredLLMClient."""
    client = MagicMock(spec=IStructuredLLMClient)
    sample_result = BatchAnalysisResult(
        findings=[
            DiagnosedFinding(
                campaign_name="US_Search_Brand",
                platform="google_ads",
                country="US",
                issue_type="DATA_QUALITY",
                confidence_score=0.95,
                root_cause_analysis="Pixel failure detected.",
                competing_hypotheses=[
                    Hypothesis(
                        statement="Pixel down",
                        supporting_evidence=["Zero conversions"],
                        contradictory_evidence=[],
                        confidence=0.95,
                        missing_evidence=[],
                    ),
                    Hypothesis(
                        statement="Creative fatigue",
                        supporting_evidence=[],
                        contradictory_evidence=["Zero conversions"],
                        confidence=0.05,
                        missing_evidence=[],
                    ),
                ],
                selected_hypothesis=Hypothesis(
                    statement="Pixel down",
                    supporting_evidence=["Zero conversions"],
                    contradictory_evidence=[],
                    confidence=0.95,
                    missing_evidence=[],
                ),
                action_plan=OperationalActionPlan(
                    budget_action="HOLD",
                    bid_action="NO_CHANGE",
                    creative_action="NO_ACTION",
                    tracking_action="AUDIT_PIXEL",
                    rationale="Data quality issue",
                    concrete_steps=["Check GTM"],
                    expected_effect="Restore tracking",
                    risk_level="LOW",
                    requires_approval=False,
                ),
                metric_change_summary="Conversions: 100 -> 0",
                business_impact_narrative="Tracking broken, spend active.",
            )
        ],
        executive_summary="Briefing text",
        overall_data_health="DEGRADED",
        analysis_timestamp="2026-09-07T12:00:00Z",
    )
    client.generate_structured_analysis = AsyncMock(return_value=sample_result)
    return client


@pytest.fixture
def sample_dossier() -> EvidenceDossier:
    """Fixture returning a complete EvidenceDossier with 8 metrics and DataQualitySignal."""
    metrics = {
        "spend": MetricEvidence(
            "spend",
            current_value=500.0,
            baseline_value=200.0,
            delta_pct=1.5,
            z_score=3.0,
            is_anomaly=True,
        ),
        "impressions": MetricEvidence(
            "impressions",
            current_value=10000.0,
            baseline_value=10000.0,
            delta_pct=0.0,
            z_score=0.0,
            is_anomaly=False,
        ),
        "clicks": MetricEvidence(
            "clicks",
            current_value=500.0,
            baseline_value=500.0,
            delta_pct=0.0,
            z_score=0.0,
            is_anomaly=False,
        ),
        "ctr": MetricEvidence(
            "ctr",
            current_value=0.05,
            baseline_value=0.05,
            delta_pct=0.0,
            z_score=0.0,
            is_anomaly=False,
        ),
        "cpc": MetricEvidence(
            "cpc",
            current_value=1.0,
            baseline_value=0.4,
            delta_pct=1.5,
            z_score=2.8,
            is_anomaly=True,
        ),
        "conversions": MetricEvidence(
            "conversions",
            current_value=0.0,
            baseline_value=50.0,
            delta_pct=-1.0,
            z_score=-4.0,
            is_anomaly=True,
        ),
        "cpa": MetricEvidence(
            "cpa",
            current_value=None,
            baseline_value=4.0,
            delta_pct=None,
            z_score=None,
            is_anomaly=False,
        ),
        "roas": MetricEvidence(
            "roas",
            current_value=0.0,
            baseline_value=3.5,
            delta_pct=-1.0,
            z_score=-4.0,
            is_anomaly=True,
        ),
    }
    dq_signal = DataQualitySignal(
        signal_type=DataQualitySignalType.ZERO_CONVERSIONS_WITH_ACTIVE_SPEND,
        is_triggered=True,
        metric_name="conversions",
        current_value=0.0,
        baseline_value=50.0,
        delta_pct=-1.0,
        factual_statement="Zero conversions recorded while active spend is $500.0.",
    )
    campaign = CampaignEvidence(
        campaign_id="cmp-123",
        campaign_name="US_Search_Brand",
        platform="google_ads",
        account_id="acc-999",
        country="US",
        spend=500.0,
        financial_impact_score=85.5,
        metrics=metrics,
        data_quality_signals=(dq_signal,),
    )
    return EvidenceDossier(
        target_date="2026-09-07",
        baseline_window="14d",
        total_anomalies_detected=4,
        total_campaigns_impacted=1,
        top_campaign_evidence=(campaign,),
    )


@pytest.fixture
def prompt_file(tmp_path: Path) -> Path:
    """Fixture creating a temporary valid prompt template file."""
    file = tmp_path / "executive_briefing.md"
    file.write_text("System Prompt: You are a lead analyst. {{anomalies_json}}", encoding="utf-8")
    return file


@pytest.mark.asyncio
async def test_orchestrator_run_success(
    mock_llm_client: MagicMock, sample_dossier: EvidenceDossier, prompt_file: Path
) -> None:
    """Verify orchestrator runs batch analysis and populates AgentContext.result."""
    context = AgentContext(
        execution_id="exec-001",
        target_date="2026-09-07",
        dossier=sample_dossier,
    )

    orchestrator = BatchReasoningOrchestrator(
        client=mock_llm_client,
        prompt_template_path=prompt_file,
    )

    result = await orchestrator.run(context)

    assert result is not None
    assert context.result == result
    assert len(result.findings) == 1
    assert result.findings[0].campaign_name == "US_Search_Brand"

    # Verify client call arguments
    mock_llm_client.generate_structured_analysis.assert_called_once()
    _, kwargs = mock_llm_client.generate_structured_analysis.call_args
    assert "System Prompt: You are a lead analyst." in kwargs["system_instruction"]

    payload = kwargs["user_prompt"]
    assert "US_Search_Brand" in payload
    assert "zero_conversions_with_active_spend" in payload
    assert "cmp-123" in payload


def test_orchestrator_dossier_serialization(
    mock_llm_client: MagicMock, sample_dossier: EvidenceDossier, prompt_file: Path
) -> None:
    """Verify dossier serialization completeness (all 8 metrics present)."""
    orchestrator = BatchReasoningOrchestrator(
        client=mock_llm_client,
        prompt_template_path=prompt_file,
    )

    json_payload = orchestrator.serialize_dossier(sample_dossier, "2026-09-07")

    assert "2026-09-07" in json_payload
    assert "14d" in json_payload
    assert "85.5" in json_payload
    # All 8 metrics present
    metrics_keys = ["spend", "impressions", "clicks", "ctr", "cpc", "conversions", "cpa", "roas"]
    for metric_key in metrics_keys:
        assert f'"{metric_key}"' in json_payload

    # Data quality signal present
    assert "Zero conversions recorded" in json_payload


@pytest.mark.asyncio
async def test_orchestrator_missing_prompt_file(
    mock_llm_client: MagicMock, sample_dossier: EvidenceDossier, tmp_path: Path
) -> None:
    """Verify missing prompt file raises AgentExecutionError."""
    missing_file = tmp_path / "missing_briefing.md"
    context = AgentContext(
        execution_id="exec-002",
        target_date="2026-09-07",
        dossier=sample_dossier,
    )
    orchestrator = BatchReasoningOrchestrator(
        client=mock_llm_client,
        prompt_template_path=missing_file,
    )

    with pytest.raises(AgentExecutionError, match="Prompt template file not found"):
        await orchestrator.run(context)


@pytest.mark.asyncio
async def test_orchestrator_empty_prompt_file(
    mock_llm_client: MagicMock, sample_dossier: EvidenceDossier, tmp_path: Path
) -> None:
    """Verify empty prompt file raises AgentExecutionError."""
    empty_file = tmp_path / "empty.md"
    empty_file.write_text("   \n", encoding="utf-8")
    context = AgentContext(
        execution_id="exec-003",
        target_date="2026-09-07",
        dossier=sample_dossier,
    )
    orchestrator = BatchReasoningOrchestrator(
        client=mock_llm_client,
        prompt_template_path=empty_file,
    )

    with pytest.raises(AgentExecutionError, match="Prompt template file is empty"):
        await orchestrator.run(context)


@pytest.mark.asyncio
async def test_orchestrator_client_error_triggers_fallback(
    mock_llm_client: MagicMock, sample_dossier: EvidenceDossier, prompt_file: Path
) -> None:
    """Verify client exception is caught and triggers fallback output."""
    mock_llm_client.generate_structured_analysis.side_effect = RuntimeError("API Network Timeout")

    context = AgentContext(
        execution_id="exec-004",
        target_date="2026-09-07",
        dossier=sample_dossier,
    )
    orchestrator = BatchReasoningOrchestrator(
        client=mock_llm_client,
        prompt_template_path=prompt_file,
    )

    result = await orchestrator.run(context)
    assert result is not None
    assert "[DETERMINISTIC FALLBACK - AGENT UNASSISTED]" in result.executive_summary
