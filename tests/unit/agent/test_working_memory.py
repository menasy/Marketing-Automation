"""Unit tests for WorkingMemory execution state tracker and orchestrator telemetry integration."""

from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent.memory.working_memory import MemoryEvent, WorkingMemory
from src.agent.runtime.context import AgentContext
from src.agent.runtime.gemini_client import IStructuredLLMClient
from src.agent.runtime.orchestrator import BatchReasoningOrchestrator
from src.agent.schemas.reasoning import (
    BatchAnalysisResult,
    DiagnosedFinding,
    Hypothesis,
    OperationalActionPlan,
)
from src.domain.models.evidence_dossier import CampaignEvidence, EvidenceDossier, MetricEvidence


def test_memory_event_immutability() -> None:
    """Verify MemoryEvent is frozen and attributes cannot be mutated."""
    event = MemoryEvent(
        timestamp="2026-09-07T12:00:00Z",
        event_type="STEP",
        description="Initial step",
        details={"step_name": "START"},
    )

    assert event.event_type == "STEP"
    assert event.details["step_name"] == "START"

    with pytest.raises(FrozenInstanceError):
        # Type ignored for runtime immutability verification test
        event.description = "Mutated step"  # type: ignore[misc]


def test_working_memory_record_step() -> None:
    """Verify record_step correctly records step transition metadata into working memory."""
    memory = WorkingMemory()
    memory.record_step("PROMPT_SERIALIZATION", "Serialized evidence dossier", campaign_count=3)

    events = memory.get_events()
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "STEP"
    assert event.description == "Serialized evidence dossier"
    assert event.details["step_name"] == "PROMPT_SERIALIZATION"
    assert event.details["campaign_count"] == 3
    assert "T" in event.timestamp


def test_working_memory_record_tool_call() -> None:
    """Verify record_tool_call records tool execution metadata."""
    memory = WorkingMemory()
    memory.record_tool_call(
        tool_name="get_campaign_metrics",
        parameters={"campaign_id": "cmp-1"},
        success=True,
        error=None,
    )

    events = memory.get_events()
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "TOOL_CALL"
    assert "get_campaign_metrics" in event.description
    assert event.details["tool_name"] == "get_campaign_metrics"
    assert event.details["parameters"] == {"campaign_id": "cmp-1"}
    assert event.details["success"] is True
    assert event.details["error"] is None


def test_working_memory_record_hypothesis() -> None:
    """Verify record_hypothesis records hypothesis evaluation details."""
    memory = WorkingMemory()
    memory.record_hypothesis(
        campaign_name="US_Search_Brand",
        statement="Pixel tracking collapsed",
        selected=True,
        confidence=0.95,
    )

    events = memory.get_events()
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "HYPOTHESIS_EVALUATION"
    assert event.details["campaign_name"] == "US_Search_Brand"
    assert event.details["statement"] == "Pixel tracking collapsed"
    assert event.details["selected"] is True
    assert event.details["confidence"] == 0.95


def test_working_memory_record_verification() -> None:
    """Verify record_verification records verification gate outcomes."""
    memory = WorkingMemory()
    memory.record_verification(
        is_valid=False,
        errors=("Numeric hallucination in CPA",),
        warnings=("High variance detected",),
    )

    events = memory.get_events()
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "VERIFICATION"
    assert event.details["is_valid"] is False
    assert event.details["errors"] == ["Numeric hallucination in CPA"]
    assert event.details["warnings"] == ["High variance detected"]


def test_working_memory_get_events_snapshot_immutability() -> None:
    """Verify get_events returns an immutable tuple snapshot."""
    memory = WorkingMemory()
    memory.record_step("STEP_1", "First step")

    snapshot = memory.get_events()
    assert len(snapshot) == 1

    # Record additional event after snapshot
    memory.record_step("STEP_2", "Second step")

    # Snapshot should remain unchanged
    assert len(snapshot) == 1
    assert len(memory.get_events()) == 2


def test_working_memory_to_dict_serialization() -> None:
    """Verify to_dict returns serialized dictionary suitable for execution logs."""
    memory = WorkingMemory()
    memory.record_step("INIT", "Pipeline started")
    memory.record_verification(is_valid=True, errors=(), warnings=())

    payload = memory.to_dict()
    assert payload["total_events"] == 2
    events = payload["events"]
    assert isinstance(events, list)
    assert len(events) == 2
    assert events[0]["event_type"] == "STEP"
    assert events[1]["event_type"] == "VERIFICATION"


def test_working_memory_clear() -> None:
    """Verify clear flushes memory events."""
    memory = WorkingMemory()
    memory.record_step("STEP_1", "Desc")
    assert len(memory.get_events()) == 1

    memory.clear()
    assert len(memory.get_events()) == 0
    assert memory.to_dict()["total_events"] == 0


def test_working_memory_exception_safety(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify memory recording methods do not raise unhandled exceptions."""

    def mock_now_raises(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Unexpected datetime clock fault")

    memory = WorkingMemory()
    monkeypatch.setattr("src.agent.memory.working_memory.datetime", MagicMock(now=mock_now_raises))

    # Recording should swallow the exception without raising
    memory.record_step("STEP_ERROR", "Should not raise exception")
    assert len(memory.get_events()) == 0


def test_agent_context_default_working_memory() -> None:
    """Verify AgentContext initializes with a default WorkingMemory instance."""
    dossier = EvidenceDossier(
        target_date="2026-09-07",
        baseline_window="14d",
        total_anomalies_detected=0,
        total_campaigns_impacted=0,
        top_campaign_evidence=(),
    )

    ctx = AgentContext(
        execution_id="exec-mem-001",
        target_date="2026-09-07",
        dossier=dossier,
    )

    assert isinstance(ctx.working_memory, WorkingMemory)
    assert len(ctx.working_memory.get_events()) == 0


@pytest.fixture
def sample_dossier() -> EvidenceDossier:
    """Fixture returning a simple EvidenceDossier."""
    metric_spend = MetricEvidence(
        metric_name="spend",
        current_value=500.0,
        baseline_value=200.0,
        delta_pct=1.5,
        z_score=3.0,
        is_anomaly=True,
    )
    campaign = CampaignEvidence(
        campaign_id="cmp-1",
        campaign_name="US_Search_Brand",
        platform="google_ads",
        account_id="acc-1",
        country="US",
        spend=500.0,
        financial_impact_score=80.0,
        metrics={"spend": metric_spend},
        data_quality_signals=(),
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
    """Fixture creating temporary valid prompt file."""
    file = tmp_path / "executive_briefing.md"
    file.write_text("System Prompt: You are a lead analyst.", encoding="utf-8")
    return file


@pytest.fixture
def valid_result() -> BatchAnalysisResult:
    """Fixture returning a valid BatchAnalysisResult."""
    hyp1 = Hypothesis(statement="Spend anomaly", confidence=0.9)
    hyp2 = Hypothesis(statement="Bidding shift", confidence=0.1)
    plan = OperationalActionPlan(
        budget_action="HOLD",
        bid_action="NO_CHANGE",
        creative_action="NO_ACTION",
        tracking_action="AUDIT",
        rationale="Audit spend",
        concrete_steps=["Check budget pacing"],
        expected_effect="Stabilize spend",
        risk_level="LOW",
        requires_approval=False,
    )
    finding = DiagnosedFinding(
        campaign_name="US_Search_Brand",
        platform="google_ads",
        country="US",
        issue_type="PERFORMANCE",
        confidence_score=0.9,
        root_cause_analysis="Spend spiked by +150.0% spend",
        competing_hypotheses=[hyp1, hyp2],
        selected_hypothesis=hyp1,
        action_plan=plan,
        metric_change_summary="Spend spiked by +150.0% spend",
        business_impact_narrative="Higher acquisition costs",
    )
    return BatchAnalysisResult(
        findings=[finding],
        executive_summary="Executive briefing narrative.",
        overall_data_health="HEALTHY",
        analysis_timestamp="2026-09-07T12:00:00Z",
    )


@pytest.fixture
def invalid_result() -> BatchAnalysisResult:
    """Fixture returning an invalid BatchAnalysisResult (hallucinated metric +500% CPC)."""
    hyp1 = Hypothesis(statement="Spend anomaly", confidence=0.9)
    hyp2 = Hypothesis(statement="Bidding shift", confidence=0.1)
    plan = OperationalActionPlan(
        budget_action="HOLD",
        bid_action="NO_CHANGE",
        creative_action="NO_ACTION",
        tracking_action="AUDIT",
        rationale="Audit spend",
        concrete_steps=["Check budget pacing"],
        expected_effect="Stabilize spend",
        risk_level="LOW",
        requires_approval=False,
    )
    finding = DiagnosedFinding(
        campaign_name="US_Search_Brand",
        platform="google_ads",
        country="US",
        issue_type="PERFORMANCE",
        confidence_score=0.9,
        root_cause_analysis="CPC spiked by +500% CPC",
        competing_hypotheses=[hyp1, hyp2],
        selected_hypothesis=hyp1,
        action_plan=plan,
        metric_change_summary="CPC spiked by +500% CPC",
        business_impact_narrative="Higher acquisition costs",
    )
    return BatchAnalysisResult(
        findings=[finding],
        executive_summary="Executive briefing narrative.",
        overall_data_health="HEALTHY",
        analysis_timestamp="2026-09-07T12:00:00Z",
    )


@pytest.mark.asyncio
async def test_orchestrator_working_memory_happy_path(
    sample_dossier: EvidenceDossier, prompt_file: Path, valid_result: BatchAnalysisResult
) -> None:
    """Verify WorkingMemory telemetry events recorded on happy path execution."""
    mock_client = MagicMock(spec=IStructuredLLMClient)
    mock_client.generate_structured_analysis = AsyncMock(return_value=valid_result)

    orchestrator = BatchReasoningOrchestrator(client=mock_client, prompt_template_path=prompt_file)
    context = AgentContext(
        execution_id="exec-wm-1", target_date="2026-09-07", dossier=sample_dossier
    )

    await orchestrator.run(context)

    events = context.working_memory.get_events()
    event_types = [e.event_type for e in events]

    assert "STEP" in event_types
    assert "VERIFICATION" in event_types
    assert "HYPOTHESIS_EVALUATION" in event_types

    # Check specific steps recorded
    step_names = [
        e.details["step_name"]
        for e in events
        if e.event_type == "STEP" and "step_name" in e.details
    ]
    assert "PROMPT_SERIALIZATION" in step_names
    assert "INITIAL_GENERATION" in step_names

    # Check hypotheses recorded
    hyp_events = [e for e in events if e.event_type == "HYPOTHESIS_EVALUATION"]
    assert len(hyp_events) == 2
    assert hyp_events[0].details["statement"] == "Spend anomaly"
    assert hyp_events[0].details["selected"] is True


@pytest.mark.asyncio
async def test_orchestrator_working_memory_reflection_retry(
    sample_dossier: EvidenceDossier,
    prompt_file: Path,
    invalid_result: BatchAnalysisResult,
    valid_result: BatchAnalysisResult,
) -> None:
    """Verify WorkingMemory telemetry records reflection retry step event."""
    mock_client = MagicMock(spec=IStructuredLLMClient)
    mock_client.generate_structured_analysis = AsyncMock(side_effect=[invalid_result, valid_result])

    orchestrator = BatchReasoningOrchestrator(client=mock_client, prompt_template_path=prompt_file)
    context = AgentContext(
        execution_id="exec-wm-2", target_date="2026-09-07", dossier=sample_dossier
    )

    await orchestrator.run(context)

    events = context.working_memory.get_events()
    event_types = [e.event_type for e in events]

    assert event_types.count("VERIFICATION") == 2

    reflection_events = [
        e
        for e in events
        if e.event_type == "STEP" and e.details.get("step_name") == "REFLECTION_RETRY"
    ]
    assert len(reflection_events) == 1
    assert "errors" in reflection_events[0].details


@pytest.mark.asyncio
async def test_orchestrator_working_memory_fallback(
    sample_dossier: EvidenceDossier, prompt_file: Path, invalid_result: BatchAnalysisResult
) -> None:
    """Verify WorkingMemory telemetry records FALLBACK_ACTIVATION on failures."""
    mock_client = MagicMock(spec=IStructuredLLMClient)
    mock_client.generate_structured_analysis = AsyncMock(
        side_effect=[invalid_result, invalid_result]
    )

    orchestrator = BatchReasoningOrchestrator(client=mock_client, prompt_template_path=prompt_file)
    context = AgentContext(
        execution_id="exec-wm-3", target_date="2026-09-07", dossier=sample_dossier
    )

    await orchestrator.run(context)

    events = context.working_memory.get_events()
    fallback_events = [
        e
        for e in events
        if e.event_type == "STEP" and e.details.get("step_name") == "FALLBACK_ACTIVATION"
    ]
    assert len(fallback_events) == 1
    assert "failure_reasons" in fallback_events[0].details
