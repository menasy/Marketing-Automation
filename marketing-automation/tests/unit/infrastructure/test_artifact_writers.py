"""Unit tests for dynamic Markdown & JSON artifact writers and ArtifactService coordinator."""

import json
from pathlib import Path

from src.agent.schemas.reasoning import (
    BatchAnalysisResult,
    DiagnosedFinding,
    Hypothesis,
    OperationalActionPlan,
)
from src.domain.models.data_quality_signal import (
    DataQualitySignal,
    DataQualitySignalType,
)
from src.domain.models.evidence_dossier import (
    CampaignEvidence,
    EvidenceDossier,
    MetricEvidence,
)
from src.infrastructure.reporting.artifact_service import ArtifactService
from src.infrastructure.reporting.briefing_writer import ExecutiveBriefingWriter
from src.infrastructure.reporting.json_exporter import JsonAnomalyExporter
from src.infrastructure.reporting.operational_report import TopFindingsReportWriter


def _create_sample_dossier() -> EvidenceDossier:
    """Helper to construct a realistic EvidenceDossier with edge-case float values."""
    metrics = {
        "conversions": MetricEvidence(
            metric_name="conversions",
            current_value=0.0,
            baseline_value=45.5,
            delta_pct=-100.0,
            z_score=-4.2,
            is_anomaly=True,
        ),
        "spend": MetricEvidence(
            metric_name="spend",
            current_value=150.0,
            baseline_value=150.0,
            delta_pct=0.0,
            z_score=0.0,
            is_anomaly=False,
        ),
        "nan_metric": MetricEvidence(
            metric_name="nan_metric",
            current_value=float("nan"),
            baseline_value=float("inf"),
            delta_pct=None,
            z_score=None,
            is_anomaly=False,
        ),
    }

    signal = DataQualitySignal(
        signal_type=DataQualitySignalType.ZERO_CONVERSIONS_WITH_ACTIVE_SPEND,
        is_triggered=True,
        metric_name="conversions",
        current_value=0.0,
        baseline_value=45.5,
        delta_pct=-100.0,
        factual_statement="Spend is active ($150) but conversions collapsed to 0.",
    )

    campaign_ev = CampaignEvidence(
        campaign_id="cmp_123",
        campaign_name="US_Google_Search_Brand",
        platform="google_ads",
        account_id="acc_99",
        country="US",
        spend=150.0,
        financial_impact_score=95.0,
        metrics=metrics,
        data_quality_signals=(signal,),
    )

    return EvidenceDossier(
        target_date="2026-09-07",
        baseline_window="D-14 to D-1",
        total_anomalies_detected=3,
        total_campaigns_impacted=1,
        top_campaign_evidence=(campaign_ev,),
    )


def _create_sample_batch_result() -> BatchAnalysisResult:
    """Helper to construct a realistic BatchAnalysisResult produced by Gemini agent."""
    selected_hyp = Hypothesis(
        statement="Google Ads Conversion Pixel/CAPI tracking breakdown on purchase event",
        supporting_evidence=[
            "Conversions dropped 100% to zero",
            "Spend remained steady at $150/day",
            "CTR is completely stable at 4.5%",
        ],
        contradictory_evidence=[],
        confidence=0.95,
        missing_evidence=["GTM debug logs for purchase event firing"],
    )

    action_plan = OperationalActionPlan(
        budget_action="HOLD_CURRENT_BUDGET",
        bid_action="NO_CHANGE",
        creative_action="NO_ACTION",
        tracking_action="AUDIT_GOOGLE_TAG_MANAGER_PURCHASE_PIXEL",
        rationale=(
            "Zero conversions with active spend and steady CTR confirms a technical tracking issue."
        ),
        concrete_steps=[
            "Verify Google Tag Manager container trigger for purchase page.",
            "Check Google Ads Conversion Health diagnosis tab for dropped tags.",
            "Send test transaction payload via Tag Assistant.",
        ],
        expected_effect="Restore conversion attribution within 2 hours",
        risk_level="LOW",
        requires_approval=False,
    )

    finding_1 = DiagnosedFinding(
        campaign_name="US_Google_Search_Brand",
        platform="google_ads",
        country="US",
        issue_type="DATA_QUALITY",
        confidence_score=0.95,
        root_cause_analysis=(
            "Abrupt conversion collapse from 45.5 to 0.0 while CTR remained steady "
            "confirms a tracking failure rather than ad fatigue."
        ),
        competing_hypotheses=[selected_hyp],
        selected_hypothesis=selected_hyp,
        action_plan=action_plan,
        metric_change_summary=(
            "CONVERSIONS: 45.5 → 0.0 (-100.0%, Z = -4.2) | SPEND: $150 → $150 (+0.0%)"
        ),
        business_impact_narrative=(
            "Data tracking failure causing false reporting of zero ROAS "
            "despite healthy user intent."
        ),
    )

    finding_2 = DiagnosedFinding(
        campaign_name="EU_Meta_Retargeting",
        platform="meta_ads",
        country="DE",
        issue_type="PERFORMANCE",
        confidence_score=0.88,
        root_cause_analysis=(
            "CPA increased by 160% driven by creative fatigue and frequency saturation above 6.5."
        ),
        competing_hypotheses=[],
        selected_hypothesis=Hypothesis(
            statement="Creative fatigue and audience exhaustion",
            supporting_evidence=["Frequency > 6.5", "CTR dropped 50%"],
            contradictory_evidence=[],
            confidence=0.88,
            missing_evidence=[],
        ),
        action_plan=OperationalActionPlan(
            budget_action="REDUCE_BUDGET_20_PERCENT",
            bid_action="CAP_TARGET_CPA",
            creative_action="ROTATE_FATIGUED_VIDEO_CREATIVES",
            tracking_action="NO_ACTION",
            rationale="Frequency saturation requiring fresh creative assets.",
            concrete_steps=["Pause adset 3", "Upload 2 new video variations"],
            expected_effect="Reduce CPA back to baseline $25",
            risk_level="MEDIUM",
            requires_approval=True,
        ),
        metric_change_summary="CPA: $25 → $65 (+160.0%) | CTR: 2.1% → 1.05% (-50.0%)",
        business_impact_narrative=(
            "Budget inefficiency resulting in $450 excess spend over baseline CPA target."
        ),
    )

    return BatchAnalysisResult(
        findings=[finding_1, finding_2],
        executive_summary=(
            "Data health status is DEGRADED due to 1 critical tracking failure in US Google Ads "
            "search campaign. Total spend at risk is estimated at $150/day."
        ),
        overall_data_health="DEGRADED",
        analysis_timestamp="2026-09-07T13:45:00Z",
    )


# =============================================================================
# JsonAnomalyExporter Tests
# =============================================================================


def test_json_anomaly_exporter_serialization(tmp_path: Path) -> None:
    """Verify JsonAnomalyExporter outputs valid JSON matching EvidenceDossier structures."""
    dossier = _create_sample_dossier()
    exporter = JsonAnomalyExporter()
    out_path = tmp_path / "anomalies.json"

    content = exporter.export_to_file(dossier, out_path)

    assert out_path.is_file()

    # Parse exported JSON to verify strict JSON schema validity
    data = json.loads(content)
    assert data["target_date"] == "2026-09-07"
    assert data["total_anomalies_detected"] == 3

    top_campaigns = data["top_campaign_evidence"]
    assert len(top_campaigns) == 1
    cmp_data = top_campaigns[0]
    assert cmp_data["campaign_name"] == "US_Google_Search_Brand"

    # Verify float NaN / Inf handled safely as null
    nan_metric = cmp_data["metrics"]["nan_metric"]
    assert nan_metric["current_value"] is None
    assert nan_metric["baseline_value"] is None


# =============================================================================
# TopFindingsReportWriter Tests
# =============================================================================


def test_top_findings_report_writer_renders_case_study_questions(tmp_path: Path) -> None:
    """Verify TopFindingsReportWriter renders Case Study Questions 1 & 2 dynamically."""
    result = _create_sample_batch_result()
    writer = TopFindingsReportWriter()
    out_path = tmp_path / "top_3_findings.md"

    content = writer.render_and_save(result, out_path)

    assert out_path.is_file()
    assert "# Executive Operational Report: Top 3 Critical Findings" in content

    # Check Question 1 & Question 2 explicit section headers
    q1 = (
        "Soru 1: Bulgu gerçek bir performans sorununa mı işaret etmektedir, "
        "yoksa verinin kendisinden mi kaynaklanmaktadır?"
    )
    q2 = "Soru 2: Bütçe, teklif veya kreatif tarafında hangi aksiyonu alırdınız?"

    assert q1 in content
    assert q2 in content

    # Check dynamic badges
    assert "[VERİ / TRACKING HATASI]" in content
    assert "[GERÇEK PERFORMANS DÜŞÜŞÜ]" in content

    # Check injected Agent rationale & concrete steps
    assert "AUDIT_GOOGLE_TAG_MANAGER_PURCHASE_PIXEL" in content
    assert "1. Verify Google Tag Manager container trigger for purchase page." in content
    assert "2. Check Google Ads Conversion Health diagnosis tab for dropped tags." in content


def test_top_findings_report_writer_enforces_top_3_limit(tmp_path: Path) -> None:
    """Verify TopFindingsReportWriter strictly caps rendered findings to max 3."""
    result = _create_sample_batch_result()
    # Duplicate findings to make 5 findings
    finding = result.findings[0]
    large_result = BatchAnalysisResult(
        findings=[finding] * 5,
        executive_summary="Multiple findings batch run",
        overall_data_health="CRITICAL",
        analysis_timestamp="2026-09-07T13:45:00Z",
    )

    writer = TopFindingsReportWriter()
    content = writer.render(large_result)

    # Count occurrences of "Finding "
    assert content.count("### Finding ") == 3


# =============================================================================
# ExecutiveBriefingWriter Tests
# =============================================================================


def test_executive_briefing_writer_renders_c_level_briefing(tmp_path: Path) -> None:
    """Verify ExecutiveBriefingWriter renders morning briefing, health badge, and impact table."""
    result = _create_sample_batch_result()
    dossier = _create_sample_dossier()

    writer = ExecutiveBriefingWriter()
    out_path = tmp_path / "sample_briefing.md"

    content = writer.render_and_save(result, out_path, dossier=dossier)

    assert out_path.is_file()
    assert "# Executive Briefing: Daily Marketing & Data Intelligence" in content
    assert "🟡 DEGRADED" in content
    assert result.executive_summary in content
    assert "| Campaign | Platform | Country | Issue Classification |" in content
    assert "US_Google_Search_Brand" in content
    assert "EU_Meta_Retargeting" in content


# =============================================================================
# ArtifactService Coordinator Tests
# =============================================================================


def test_artifact_service_write_all_atomic_delivery(tmp_path: Path) -> None:
    """Verify ArtifactService creates missing directory and atomically writes all 3 deliverables."""
    dossier = _create_sample_dossier()
    result = _create_sample_batch_result()

    target_dir = tmp_path / "nested" / "output_dir"
    service = ArtifactService()

    anomalies_path, top_findings_path, briefing_path = service.write_all(
        dossier, result, target_dir
    )

    assert target_dir.is_dir()
    assert anomalies_path.is_file()
    assert top_findings_path.is_file()
    assert briefing_path.is_file()

    assert anomalies_path.name == "anomalies.json"
    assert top_findings_path.name == "top_3_findings.md"
    assert briefing_path.name == "sample_briefing.md"

    # Verify JSON content is valid
    json_data = json.loads(anomalies_path.read_text(encoding="utf-8"))
    assert json_data["target_date"] == "2026-09-07"

    # Verify Markdown contents are non-empty
    assert "Executive Operational Report" in top_findings_path.read_text(encoding="utf-8")
    assert "Executive Briefing" in briefing_path.read_text(encoding="utf-8")
