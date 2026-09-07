"""Unit tests for Pydantic v2 reasoning schema contracts."""

import pytest
from pydantic import ValidationError

from src.agent.schemas.reasoning import (
    BatchAnalysisResult,
    DiagnosedFinding,
    Hypothesis,
    OperationalActionPlan,
)


def test_hypothesis_confidence_validation() -> None:
    """Verify confidence field is constrained between 0.0 and 1.0."""
    valid_hyp = Hypothesis(
        statement="Pixel tracking failure",
        supporting_evidence=["Conversions dropped to zero", "Active spend $1500"],
        contradictory_evidence=[],
        confidence=0.95,
        missing_evidence=["Server CAPI logs"],
    )
    assert valid_hyp.confidence == 0.95

    # Test underflow boundary
    with pytest.raises(ValidationError):
        Hypothesis(
            statement="Invalid",
            confidence=-0.1,
        )

    # Test overflow boundary
    with pytest.raises(ValidationError):
        Hypothesis(
            statement="Invalid",
            confidence=1.1,
        )


def test_diagnosed_finding_confidence_score_validation() -> None:
    """Verify confidence_score field is constrained between 0.0 and 1.0."""
    hyp = Hypothesis(
        statement="Creative fatigue",
        confidence=0.8,
    )
    plan = OperationalActionPlan(
        budget_action="DECREASE_20_PERCENT",
        bid_action="NO_CHANGE",
        creative_action="ROTATE_CREATIVES",
        tracking_action="NO_ACTION",
        rationale="CTR dropped 60%",
        concrete_steps=["Pause adset 1", "Upload 3 new video ads"],
        expected_effect="ROAS recovery to >2.5",
        risk_level="MEDIUM",
        requires_approval=True,
    )

    valid_finding = DiagnosedFinding(
        campaign_name="US_Search_Brand",
        platform="google_ads",
        country="US",
        issue_type="PERFORMANCE",
        confidence_score=0.85,
        root_cause_analysis="Ad fatigue observed over last 7 days.",
        selected_hypothesis=hyp,
        action_plan=plan,
        metric_change_summary="CTR: 3.2% → 0.8% (-75%)",
        business_impact_narrative="Risk of CPA inflation.",
    )
    assert valid_finding.confidence_score == 0.85

    # Test overflow boundary
    with pytest.raises(ValidationError):
        DiagnosedFinding(
            campaign_name="US_Search_Brand",
            platform="google_ads",
            country="US",
            issue_type="PERFORMANCE",
            confidence_score=1.5,
            root_cause_analysis="Invalid",
            selected_hypothesis=hyp,
            action_plan=plan,
            metric_change_summary="Summary",
            business_impact_narrative="Impact",
        )


def test_batch_analysis_result_json_parsing() -> None:
    """Verify parsing valid JSON payload into BatchAnalysisResult."""
    json_data = """
    {
        "findings": [
            {
                "campaign_name": "Meta_Retargeting_EU",
                "platform": "meta_ads",
                "country": "DE",
                "issue_type": "DATA_QUALITY",
                "confidence_score": 0.98,
                "root_cause_analysis": "CAPI event stream stopped at 14:00 GMT.",
                "competing_hypotheses": [
                    {
                        "statement": "CAPI Server Failure",
                        "supporting_evidence": ["Zero conversions", "CTR unchanged"],
                        "contradictory_evidence": [],
                        "confidence": 0.98,
                        "missing_evidence": []
                    }
                ],
                "selected_hypothesis": {
                    "statement": "CAPI Server Failure",
                    "supporting_evidence": ["Zero conversions", "CTR unchanged"],
                    "contradictory_evidence": [],
                    "confidence": 0.98,
                    "missing_evidence": []
                },
                "action_plan": {
                    "budget_action": "HOLD_CURRENT_BUDGET",
                    "bid_action": "NO_CHANGE",
                    "creative_action": "NO_ACTION",
                    "tracking_action": "AUDIT_CAPI_ACCESS_TOKEN",
                    "rationale": "Data tracking issue, do not modify campaign budget.",
                    "concrete_steps": ["Verify Meta Pixel Helper", "Refresh Graph API token"],
                    "expected_effect": "Attribution restoration",
                    "risk_level": "LOW",
                    "requires_approval": false
                },
                "metric_change_summary": "Conversions: 120 → 0 (-100%)",
                "business_impact_narrative": "ROI misattribution risk."
            }
        ],
        "executive_summary": "Günaydın Ekip, veri kalitesi sorunları tespit edildi.",
        "overall_data_health": "DEGRADED",
        "analysis_timestamp": "2026-09-07T12:00:00Z"
    }
    """

    result = BatchAnalysisResult.model_validate_json(json_data)
    assert len(result.findings) == 1
    assert result.findings[0].campaign_name == "Meta_Retargeting_EU"
    assert result.findings[0].issue_type == "DATA_QUALITY"
    assert result.overall_data_health == "DEGRADED"
    assert "Günaydın Ekip" in result.executive_summary


def test_batch_analysis_result_json_schema_export() -> None:
    """Verify BatchAnalysisResult exports a valid Pydantic v2 JSON Schema for Gemini."""
    schema = BatchAnalysisResult.model_json_schema()

    assert schema["type"] == "object"
    assert "findings" in schema["properties"]
    assert "executive_summary" in schema["properties"]
    assert "overall_data_health" in schema["properties"]

    # Verify descriptions are present on properties
    assert "description" in schema["properties"]["executive_summary"]
    assert "description" in schema["properties"]["overall_data_health"]

    # Verify nested definition exists for DiagnosedFinding
    assert "$defs" in schema
    assert "DiagnosedFinding" in schema["$defs"]
    assert "Hypothesis" in schema["$defs"]
    assert "OperationalActionPlan" in schema["$defs"]
