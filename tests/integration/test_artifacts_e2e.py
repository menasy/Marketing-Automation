"""End-to-end integration test suite validating physical creation, format integrity,
and case study compliance of output deliverables.
"""

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


def _build_e2e_dossier() -> EvidenceDossier:
    """Build a realistic multi-campaign EvidenceDossier with complete metric suites."""
    metrics_cmp1 = {
        "spend": MetricEvidence(
            metric_name="spend",
            current_value=250.0,
            baseline_value=250.0,
            delta_pct=0.0,
            z_score=0.0,
            is_anomaly=False,
        ),
        "impressions": MetricEvidence(
            metric_name="impressions",
            current_value=12500.0,
            baseline_value=12000.0,
            delta_pct=4.17,
            z_score=0.35,
            is_anomaly=False,
        ),
        "clicks": MetricEvidence(
            metric_name="clicks",
            current_value=500.0,
            baseline_value=480.0,
            delta_pct=4.17,
            z_score=0.40,
            is_anomaly=False,
        ),
        "ctr": MetricEvidence(
            metric_name="ctr",
            current_value=0.04,
            baseline_value=0.04,
            delta_pct=0.0,
            z_score=0.0,
            is_anomaly=False,
        ),
        "cpc": MetricEvidence(
            metric_name="cpc",
            current_value=0.50,
            baseline_value=0.52,
            delta_pct=-3.85,
            z_score=-0.25,
            is_anomaly=False,
        ),
        "cpm": MetricEvidence(
            metric_name="cpm",
            current_value=20.0,
            baseline_value=20.83,
            delta_pct=-3.98,
            z_score=-0.30,
            is_anomaly=False,
        ),
        "conversions": MetricEvidence(
            metric_name="conversions",
            current_value=0.0,
            baseline_value=50.0,
            delta_pct=-100.0,
            z_score=-4.2,
            is_anomaly=True,
        ),
        "cpa": MetricEvidence(
            metric_name="cpa",
            current_value=None,
            baseline_value=5.0,
            delta_pct=None,
            z_score=None,
            is_anomaly=True,
        ),
        "roas": MetricEvidence(
            metric_name="roas",
            current_value=0.0,
            baseline_value=3.5,
            delta_pct=-100.0,
            z_score=-3.8,
            is_anomaly=True,
        ),
    }

    signal_cmp1 = DataQualitySignal(
        signal_type=DataQualitySignalType.ZERO_CONVERSIONS_WITH_ACTIVE_SPEND,
        is_triggered=True,
        metric_name="conversions",
        current_value=0.0,
        baseline_value=50.0,
        delta_pct=-100.0,
        factual_statement="Active spend ($250) with 0 conversions detected.",
    )

    campaign1 = CampaignEvidence(
        campaign_id="cmp_001",
        campaign_name="US_Google_Search_Brand",
        platform="google_ads",
        account_id="acc_google_us",
        country="US",
        spend=250.0,
        financial_impact_score=195.0,
        metrics=metrics_cmp1,
        data_quality_signals=(signal_cmp1,),
    )

    metrics_cmp2 = {
        "spend": MetricEvidence(
            metric_name="spend",
            current_value=600.0,
            baseline_value=400.0,
            delta_pct=50.0,
            z_score=2.8,
            is_anomaly=True,
        ),
        "impressions": MetricEvidence(
            metric_name="impressions",
            current_value=15000.0,
            baseline_value=20000.0,
            delta_pct=-25.0,
            z_score=-1.9,
            is_anomaly=False,
        ),
        "clicks": MetricEvidence(
            metric_name="clicks",
            current_value=150.0,
            baseline_value=300.0,
            delta_pct=-50.0,
            z_score=-2.5,
            is_anomaly=True,
        ),
        "ctr": MetricEvidence(
            metric_name="ctr",
            current_value=0.01,
            baseline_value=0.015,
            delta_pct=-33.33,
            z_score=-2.1,
            is_anomaly=True,
        ),
        "cpc": MetricEvidence(
            metric_name="cpc",
            current_value=4.0,
            baseline_value=1.33,
            delta_pct=200.75,
            z_score=3.5,
            is_anomaly=True,
        ),
        "cpm": MetricEvidence(
            metric_name="cpm",
            current_value=40.0,
            baseline_value=20.0,
            delta_pct=100.0,
            z_score=3.1,
            is_anomaly=True,
        ),
        "conversions": MetricEvidence(
            metric_name="conversions",
            current_value=10.0,
            baseline_value=25.0,
            delta_pct=-60.0,
            z_score=-2.9,
            is_anomaly=True,
        ),
        "cpa": MetricEvidence(
            metric_name="cpa",
            current_value=60.0,
            baseline_value=16.0,
            delta_pct=275.0,
            z_score=3.8,
            is_anomaly=True,
        ),
        "roas": MetricEvidence(
            metric_name="roas",
            current_value=0.8,
            baseline_value=2.4,
            delta_pct=-66.67,
            z_score=-3.0,
            is_anomaly=True,
        ),
    }

    signal_cmp2 = DataQualitySignal(
        signal_type=DataQualitySignalType.COST_SPIKE_VOLUME_DROP,
        is_triggered=True,
        metric_name="cpa",
        current_value=60.0,
        baseline_value=16.0,
        delta_pct=275.0,
        factual_statement="CPA spiked +275% while conversion volume dropped 60%.",
    )

    campaign2 = CampaignEvidence(
        campaign_id="cmp_002",
        campaign_name="EU_Meta_Prospecting_Video",
        platform="meta_ads",
        account_id="acc_meta_eu",
        country="DE",
        spend=600.0,
        financial_impact_score=165.0,
        metrics=metrics_cmp2,
        data_quality_signals=(signal_cmp2,),
    )

    return EvidenceDossier(
        target_date="2026-09-07",
        baseline_window="D-14 to D-1",
        total_anomalies_detected=11,
        total_campaigns_impacted=2,
        top_campaign_evidence=(campaign1, campaign2),
    )


def _build_e2e_batch_result() -> BatchAnalysisResult:
    """Build a realistic BatchAnalysisResult matching the evidence dossier."""
    hyp1 = Hypothesis(
        statement="Google Ads Conversion CAPI/Pixel breakdown on checkout page",
        supporting_evidence=[
            "Conversions collapsed 100% to 0",
            "CTR steady at 4.0%",
            "Spend and clicks remained active",
        ],
        contradictory_evidence=[],
        confidence=0.96,
        missing_evidence=["Server-side CAPI event log payload verification"],
    )

    action1 = OperationalActionPlan(
        budget_action="HOLD_CURRENT_BUDGET",
        bid_action="NO_CHANGE",
        creative_action="NO_ACTION",
        tracking_action="AUDIT_GOOGLE_TAG_MANAGER_PURCHASE_PIXEL",
        rationale=(
            "Conversions dropped to zero while CTR and spend remained completely stable, "
            "confirming a tracking breakdown rather than performance degradation."
        ),
        concrete_steps=[
            "Inspect GTM container trigger firing state on checkout confirmation page.",
            "Verify CAPI server endpoint response status codes.",
            "Publish container fix and trigger test purchase verification payload.",
        ],
        expected_effect="Restore conversion tracking attribution within 2 hours",
        risk_level="LOW",
        requires_approval=False,
    )

    finding1 = DiagnosedFinding(
        campaign_name="US_Google_Search_Brand",
        platform="google_ads",
        country="US",
        issue_type="DATA_QUALITY",
        confidence_score=0.96,
        root_cause_analysis=(
            "Abrupt conversion collapse from 50.0 to 0.0 with steady click volume (500 clicks) "
            "indicates a technical tracking failure rather than ad fatigue."
        ),
        competing_hypotheses=[hyp1],
        selected_hypothesis=hyp1,
        action_plan=action1,
        metric_change_summary=(
            "CONVERSIONS: 50.0 → 0.0 (-100.0%, Z = -4.2) | SPEND: $250 → $250 (+0.0%)"
        ),
        business_impact_narrative="False reporting of zero ROAS despite active user acquisition.",
    )

    hyp2 = Hypothesis(
        statement="Ad creative saturation and audience frequency exhaustion",
        supporting_evidence=[
            "CPM increased 100% to $40",
            "CPA spiked 275% to $60",
            "CTR dropped 33%",
        ],
        contradictory_evidence=[],
        confidence=0.89,
        missing_evidence=["Frequency breakdown by ad set"],
    )

    action2 = OperationalActionPlan(
        budget_action="REDUCE_BUDGET_20_PERCENT",
        bid_action="CAP_TARGET_CPA_AT_BASELINE",
        creative_action="ROTATE_FATIGUED_VIDEO_CREATIVES",
        tracking_action="NO_ACTION",
        rationale="Frequency saturation requiring fresh creative assets and temporary budget trim.",
        concrete_steps=[
            "Pause high-frequency ad sets in DE retargeting campaign.",
            "Deploy 3 new UGC video creative variants.",
            "Re-evaluate CPA after 48 hours.",
        ],
        expected_effect="Reduce CPA back toward baseline $16.00",
        risk_level="MEDIUM",
        requires_approval=True,
    )

    finding2 = DiagnosedFinding(
        campaign_name="EU_Meta_Prospecting_Video",
        platform="meta_ads",
        country="DE",
        issue_type="PERFORMANCE",
        confidence_score=0.89,
        root_cause_analysis=(
            "CPA increased by 275% driven by severe CPM inflation and creative fatigue."
        ),
        competing_hypotheses=[hyp2],
        selected_hypothesis=hyp2,
        action_plan=action2,
        metric_change_summary="CPA: $16 → $60 (+275.0%) | CONVERSIONS: 25 → 10 (-60.0%)",
        business_impact_narrative=(
            "Budget inefficiency resulting in $440 excess spend above CPA target."
        ),
    )

    return BatchAnalysisResult(
        findings=[finding1, finding2],
        executive_summary=(
            "Data health status is DEGRADED due to 1 critical conversion tracking breakdown in US "
            "Google Ads search campaign ($250/day spend). Additionally, 1 Meta Ads campaign in DE "
            "exhibits performance fatigue requiring creative rotation."
        ),
        overall_data_health="DEGRADED",
        analysis_timestamp="2026-09-07T13:50:00Z",
    )


# =============================================================================
# End-to-End Artifact Validation Tests
# =============================================================================


def test_e2e_artifact_generation_and_validation(tmp_path: Path) -> None:
    """Execute ArtifactService.write_all and verify physical creation of all 4 deliverables."""
    dossier = _build_e2e_dossier()
    result = _build_e2e_batch_result()
    target_dir = tmp_path / "deliverables"

    service = ArtifactService()
    anomalies_path, op_path, top_findings_path, briefing_path = service.write_all(
        dossier, result, target_dir
    )

    assert target_dir.is_dir()
    assert anomalies_path.is_file() and anomalies_path.stat().st_size > 0
    assert op_path.is_file() and op_path.stat().st_size > 0
    assert top_findings_path.is_file() and top_findings_path.stat().st_size > 0
    assert briefing_path.is_file() and briefing_path.stat().st_size > 0

    assert op_path.name == "operational_assessment.md"
    assert top_findings_path.name == "top_3_findings.md"
    assert op_path.read_text(encoding="utf-8") == top_findings_path.read_text(encoding="utf-8")


def test_anomalies_json_structure_and_types(tmp_path: Path) -> None:
    """Validate output/anomalies.json physical format, schema keys, and clean numeric typing."""
    dossier = _build_e2e_dossier()
    result = _build_e2e_batch_result()
    target_dir = tmp_path / "deliverables"

    service = ArtifactService()
    anomalies_path, _, _, _ = service.write_all(dossier, result, target_dir)

    content = anomalies_path.read_text(encoding="utf-8")
    data = json.loads(content)

    assert isinstance(data, dict)
    assert data["target_date"] == "2026-09-07"
    assert data["baseline_window"] == "D-14 to D-1"
    assert data["total_anomalies_detected"] == 11
    assert data["total_campaigns_impacted"] == 2
    assert "top_campaign_evidence" in data
    assert "campaigns" in data

    campaigns = data["campaigns"]
    assert isinstance(campaigns, list)
    assert len(campaigns) == 2

    for cmp in campaigns:
        assert isinstance(cmp["campaign_name"], str)
        assert isinstance(cmp["platform"], str)
        assert isinstance(cmp["country"], str)
        assert isinstance(cmp["spend"], (int, float))
        assert isinstance(cmp["financial_impact_score"], (int, float))

        metrics = cmp["metrics"]
        assert isinstance(metrics, dict)
        for m_name, m_val in metrics.items():
            assert m_val["metric_name"] == m_name
            # Ensure numbers are float, int, or None (never stringified "NaN" or "Infinity")
            assert m_val["current_value"] is None or isinstance(
                m_val["current_value"], (int, float)
            )
            assert m_val["baseline_value"] is None or isinstance(
                m_val["baseline_value"], (int, float)
            )
            assert m_val["delta_pct"] is None or isinstance(m_val["delta_pct"], (int, float))
            assert m_val["z_score"] is None or isinstance(m_val["z_score"], (int, float))
            assert isinstance(m_val["is_anomaly"], bool)


def test_top_3_findings_md_case_study_questions_compliance(tmp_path: Path) -> None:
    """Validate operational_assessment.md structure & Case Study Question compliance."""
    dossier = _build_e2e_dossier()
    result = _build_e2e_batch_result()
    target_dir = tmp_path / "deliverables"

    service = ArtifactService()
    _, op_path, top_findings_path, _ = service.write_all(dossier, result, target_dir)

    assert op_path.is_file() and op_path.stat().st_size > 0
    assert top_findings_path.is_file() and top_findings_path.stat().st_size > 0

    op_content = op_path.read_text(encoding="utf-8")
    top_content = top_findings_path.read_text(encoding="utf-8")

    # Assert dual synchronized alias parity
    assert op_content == top_content

    # Header hierarchy assertions
    assert op_content.startswith("# Operasyonel Yönetici Raporu: En Kritik 3 Bulgu")
    assert "### Özet Matrisi" in op_content
    assert "## Detaylı Operasyonel Analiz ve Aksiyon Çerçevesi" in op_content

    # Max 3 findings constraint check
    finding_headers = [
        line
        for line in op_content.splitlines()
        if line.startswith("## Bulgu ")
        or line.startswith("### Bulgu ")
        or line.startswith("### Finding ")
    ]
    assert len(finding_headers) <= 3
    assert len(finding_headers) == 2

    # Case Study Question 1 assertions
    q1_text = (
        "Soru 1: Bulgu gerçek bir performans sorununa mı işaret etmektedir, "
        "yoksa verinin kendisinden mi kaynaklanmaktadır?"
    )
    assert q1_text in op_content
    assert "[VERİ / TRACKING HATASI]" in op_content
    assert "[GERÇEK PERFORMANS DÜŞÜŞÜ]" in op_content
    assert "Kök Neden Analizi:" in op_content
    assert "Seçilen Hipotez:" in op_content
    assert "Eksik Kanıt:" in op_content

    # Case Study Question 2 assertions
    q2_text = "Soru 2: Bütçe, teklif veya kreatif tarafında hangi aksiyonu alırdınız?"
    assert q2_text in op_content
    assert "Bütçe Aksiyonu" in op_content
    assert "Teklif Aksiyonu" in op_content
    assert "Kreatif Aksiyonu" in op_content
    assert "Takip Aksiyonu" in op_content
    assert "Aksiyon Gerekçesi" in op_content
    assert "Somut Operasyonel Adımlar:" in op_content
    assert "1. Inspect GTM container trigger" in op_content
    assert "2. Verify CAPI server endpoint" in op_content

    # Length & Scannability bounds check (Max 1200 words / <= 1.5 pages)
    words = op_content.split()
    assert len(words) <= 1200, f"Report word count ({len(words)}) exceeds scannability bounds"


def test_sample_briefing_md_structure(tmp_path: Path) -> None:
    """Validate output/sample_briefing.md physical structure and data health table."""
    dossier = _build_e2e_dossier()
    result = _build_e2e_batch_result()
    target_dir = tmp_path / "deliverables"

    service = ArtifactService()
    _, _, _, briefing_path = service.write_all(dossier, result, target_dir)

    content = briefing_path.read_text(encoding="utf-8")

    assert "# Yönetici Brifingi: Günlük Pazarlama ve Veri İstihbaratı" in content
    assert "🟡 DÜŞÜK PERFORMANS" in content
    assert "Hedef Analiz Tarihi" in content
    assert "2026-09-07" in content
    assert "## Yönetici Özet Narratifi" in content
    assert result.executive_summary in content
    assert "## Portföy Etki Özeti" in content
    assert "| Kampanya | Platform | Ülke | Teşhis Sınıfı | Güven |" in content
    assert "US_Google_Search_Brand" in content
    assert "EU_Meta_Prospecting_Video" in content
