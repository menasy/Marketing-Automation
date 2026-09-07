"""Unit tests for deterministic audit verifier guardrail layer."""

import pytest

from src.agent.guardrails.verifier import (
    OutputVerifier,
    UnsupportedClaimRule,
    VerificationResult,
)
from src.agent.schemas.reasoning import (
    BatchAnalysisResult,
    DiagnosedFinding,
    Hypothesis,
    OperationalActionPlan,
)
from src.domain.models.data_quality_signal import DataQualitySignal, DataQualitySignalType
from src.domain.models.evidence_dossier import CampaignEvidence, EvidenceDossier, MetricEvidence


@pytest.fixture
def valid_dossier() -> EvidenceDossier:
    """Fixture providing a valid ground-truth EvidenceDossier."""
    cpa_metric = MetricEvidence(
        metric_name="cpa",
        current_value=35.2,
        baseline_value=10.0,
        delta_pct=252.3,
        z_score=3.5,
        is_anomaly=True,
    )
    conv_metric = MetricEvidence(
        metric_name="conversions",
        current_value=0.0,
        baseline_value=50.0,
        delta_pct=-57.14,
        z_score=-4.0,
        is_anomaly=True,
    )
    spend_metric = MetricEvidence(
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
        delta_pct=-57.14,
        factual_statement="Zero conversions with active spend $1500.0.",
    )
    campaign = CampaignEvidence(
        campaign_id="cmp-001",
        campaign_name="US_Search_Brand",
        platform="google_ads",
        account_id="acc-101",
        country="US",
        spend=1500.0,
        financial_impact_score=90.0,
        metrics={
            "cpa": cpa_metric,
            "conversions": conv_metric,
            "spend": spend_metric,
        },
        data_quality_signals=(dq_signal,),
    )
    return EvidenceDossier(
        target_date="2026-09-07",
        baseline_window="14d",
        total_anomalies_detected=2,
        total_campaigns_impacted=1,
        top_campaign_evidence=(campaign,),
    )


@pytest.fixture
def valid_batch_result() -> BatchAnalysisResult:
    """Fixture providing a valid BatchAnalysisResult matching valid_dossier."""
    hyp1 = Hypothesis(
        statement="Pixel tracking outage",
        supporting_evidence=["Conversions dropped by -57.14%"],
        contradictory_evidence=[],
        confidence=0.9,
        missing_evidence=[],
    )
    hyp2 = Hypothesis(
        statement="Funnel conversion drop",
        supporting_evidence=["CPA spiked to $35.2"],
        contradictory_evidence=[],
        confidence=0.1,
        missing_evidence=[],
    )
    action_plan = OperationalActionPlan(
        budget_action="HOLD",
        bid_action="NO_CHANGE",
        creative_action="NO_ACTION",
        tracking_action="AUDIT_PIXEL",
        rationale="Tracking failure suspected",
        concrete_steps=["Check GTM container", "Verify CAPI endpoint"],
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
        root_cause_analysis="CPA rose with conversions dropping by -57.14%",
        competing_hypotheses=[hyp1, hyp2],
        selected_hypothesis=hyp1,
        action_plan=action_plan,
        metric_change_summary="Conversions dropped by -57.14% with spend of $1500",
        business_impact_narrative="High impact on tracking accuracy.",
    )
    return BatchAnalysisResult(
        findings=[finding],
        executive_summary="Summary",
        overall_data_health="DEGRADED",
        analysis_timestamp="2026-09-07T12:00:00Z",
    )


def test_valid_batch_analysis_result_passes(
    valid_batch_result: BatchAnalysisResult, valid_dossier: EvidenceDossier
) -> None:
    """Verify a valid BatchAnalysisResult passes verification with is_valid=True."""
    verifier = OutputVerifier()
    res: VerificationResult = verifier.verify(valid_batch_result, valid_dossier)
    assert res.is_valid is True
    assert len(res.errors) == 0


def test_numeric_hallucination_detection(
    valid_batch_result: BatchAnalysisResult, valid_dossier: EvidenceDossier
) -> None:
    """Verify numeric hallucination (citing +300% CPA when evidence says +252.3%) is flagged."""
    finding = valid_batch_result.findings[0]
    bad_finding = DiagnosedFinding(
        campaign_name=finding.campaign_name,
        platform=finding.platform,
        country=finding.country,
        issue_type=finding.issue_type,
        confidence_score=finding.confidence_score,
        root_cause_analysis="CPA spiked by +300% CPA",
        competing_hypotheses=finding.competing_hypotheses,
        selected_hypothesis=finding.selected_hypothesis,
        action_plan=finding.action_plan,
        metric_change_summary="CPA increased by +300% CPA",
        business_impact_narrative=finding.business_impact_narrative,
    )
    bad_result = BatchAnalysisResult(
        findings=[bad_finding],
        executive_summary=valid_batch_result.executive_summary,
        overall_data_health=valid_batch_result.overall_data_health,
        analysis_timestamp=valid_batch_result.analysis_timestamp,
    )

    verifier = OutputVerifier()
    res = verifier.verify(bad_result, valid_dossier)
    assert res.is_valid is False
    assert any("cited percentage 300.0%" in err for err in res.errors)


def test_rounded_percentage_tolerance_matching(
    valid_batch_result: BatchAnalysisResult, valid_dossier: EvidenceDossier
) -> None:
    """Verify fuzzy percentage matching within absolute +-1.0% tolerance."""
    finding = valid_batch_result.findings[0]
    rounded_hyp = Hypothesis(
        statement="Pixel outage",
        supporting_evidence=[],
        contradictory_evidence=[],
        confidence=0.9,
        missing_evidence=[],
    )
    rounded_finding = DiagnosedFinding(
        campaign_name=finding.campaign_name,
        platform=finding.platform,
        country=finding.country,
        issue_type=finding.issue_type,
        confidence_score=finding.confidence_score,
        root_cause_analysis="Conversions dropped -57.1%",
        competing_hypotheses=finding.competing_hypotheses,
        selected_hypothesis=rounded_hyp,
        action_plan=finding.action_plan,
        metric_change_summary="Conversions dropped by -57.1%",
        business_impact_narrative=finding.business_impact_narrative,
    )
    rounded_result = BatchAnalysisResult(
        findings=[rounded_finding],
        executive_summary=valid_batch_result.executive_summary,
        overall_data_health=valid_batch_result.overall_data_health,
        analysis_timestamp=valid_batch_result.analysis_timestamp,
    )

    verifier = OutputVerifier()
    res = verifier.verify(rounded_result, valid_dossier)
    assert res.is_valid is True
    assert len(res.errors) == 0


def test_currency_hallucination_detection(
    valid_batch_result: BatchAnalysisResult, valid_dossier: EvidenceDossier
) -> None:
    """Verify cited currency figures not present in dossier trigger hallucination error."""
    finding = valid_batch_result.findings[0]
    bad_finding = DiagnosedFinding(
        campaign_name=finding.campaign_name,
        platform=finding.platform,
        country=finding.country,
        issue_type=finding.issue_type,
        confidence_score=finding.confidence_score,
        root_cause_analysis="Spend inflated to $9999.0",
        competing_hypotheses=finding.competing_hypotheses,
        selected_hypothesis=finding.selected_hypothesis,
        action_plan=finding.action_plan,
        metric_change_summary="Spend was $9999.0",
        business_impact_narrative="Loss of $9999.0",
    )
    bad_result = BatchAnalysisResult(
        findings=[bad_finding],
        executive_summary="Summary",
        overall_data_health="DEGRADED",
        analysis_timestamp="2026-09-07T12:00:00Z",
    )

    verifier = OutputVerifier()
    res = verifier.verify(bad_result, valid_dossier)
    assert res.is_valid is False
    assert any("cited currency figure $9999.0" in err for err in res.errors)


def test_plain_number_hallucination_detection(
    valid_batch_result: BatchAnalysisResult, valid_dossier: EvidenceDossier
) -> None:
    """Verify cited plain decimal numbers not matching dossier trigger hallucination error."""
    finding = valid_batch_result.findings[0]
    bad_finding = DiagnosedFinding(
        campaign_name=finding.campaign_name,
        platform=finding.platform,
        country=finding.country,
        issue_type=finding.issue_type,
        confidence_score=finding.confidence_score,
        root_cause_analysis="Z-score anomaly of +88.5 detected",
        competing_hypotheses=finding.competing_hypotheses,
        selected_hypothesis=finding.selected_hypothesis,
        action_plan=finding.action_plan,
        metric_change_summary="Z-score +88.5",
        business_impact_narrative="Impact",
    )
    bad_result = BatchAnalysisResult(
        findings=[bad_finding],
        executive_summary="Summary",
        overall_data_health="DEGRADED",
        analysis_timestamp="2026-09-07T12:00:00Z",
    )

    verifier = OutputVerifier()
    res = verifier.verify(bad_result, valid_dossier)
    assert res.is_valid is False
    assert any("cited numeric value 88.5" in err for err in res.errors)


def test_ungrounded_data_quality_diagnosis(
    valid_batch_result: BatchAnalysisResult,
) -> None:
    """Verify DATA_QUALITY diagnosis on a campaign with healthy/no technical signals fails."""
    healthy_metric = MetricEvidence(
        metric_name="conversions",
        current_value=100.0,
        baseline_value=100.0,
        delta_pct=0.0,
        z_score=0.0,
        is_anomaly=False,
    )
    healthy_campaign = CampaignEvidence(
        campaign_id="cmp-002",
        campaign_name="Healthy_Campaign",
        platform="google_ads",
        account_id="acc-102",
        country="US",
        spend=500.0,
        financial_impact_score=0.0,
        metrics={"conversions": healthy_metric},
        data_quality_signals=(),
    )
    healthy_dossier = EvidenceDossier(
        target_date="2026-09-07",
        baseline_window="14d",
        total_anomalies_detected=0,
        total_campaigns_impacted=0,
        top_campaign_evidence=(healthy_campaign,),
    )

    hyp1 = Hypothesis(statement="Faulty Pixel", confidence=0.8)
    hyp2 = Hypothesis(statement="Creative Issue", confidence=0.2)
    bad_finding = DiagnosedFinding(
        campaign_name="Healthy_Campaign",
        platform="google_ads",
        country="US",
        issue_type="DATA_QUALITY",
        confidence_score=0.8,
        root_cause_analysis="Claiming pixel issue without evidence",
        competing_hypotheses=[hyp1, hyp2],
        selected_hypothesis=hyp1,
        action_plan=valid_batch_result.findings[0].action_plan,
        metric_change_summary="No changes",
        business_impact_narrative="None",
    )
    bad_result = BatchAnalysisResult(
        findings=[bad_finding],
        executive_summary="Summary",
        overall_data_health="HEALTHY",
        analysis_timestamp="2026-09-07T12:00:00Z",
    )

    verifier = OutputVerifier()
    res = verifier.verify(bad_result, healthy_dossier)
    assert res.is_valid is False
    assert any(
        "DATA_QUALITY diagnosis ungrounded: no technical or tracking signals" in err
        for err in res.errors
    )


def test_performance_issue_type_grounding(
    valid_batch_result: BatchAnalysisResult,
) -> None:
    """Verify PERFORMANCE issue_type grounding validation for degraded and healthy campaigns."""

    degraded_ctr = MetricEvidence(
        metric_name="ctr",
        current_value=0.01,
        baseline_value=0.05,
        delta_pct=-80.0,
        z_score=-3.0,
        is_anomaly=True,
    )
    degraded_campaign = CampaignEvidence(
        campaign_id="cmp-perf",
        campaign_name="Perf_Campaign",
        platform="meta_ads",
        account_id="acc-201",
        country="US",
        spend=500.0,
        financial_impact_score=50.0,
        metrics={"ctr": degraded_ctr},
        data_quality_signals=(),
    )
    degraded_dossier = EvidenceDossier(
        target_date="2026-09-07",
        baseline_window="14d",
        total_anomalies_detected=1,
        total_campaigns_impacted=1,
        top_campaign_evidence=(degraded_campaign,),
    )

    hyp1 = Hypothesis(
        statement="Ad Fatigue",
        confidence=0.7,
        missing_evidence=["Kreatif bazında performans verisi eksiktir."],
    )
    hyp2 = Hypothesis(statement="Bid Competition", confidence=0.3)
    perf_finding = DiagnosedFinding(
        campaign_name="Perf_Campaign",
        platform="meta_ads",
        country="US",
        issue_type="PERFORMANCE",
        confidence_score=0.7,
        root_cause_analysis="CTR dropped by -80.0%",
        competing_hypotheses=[hyp1, hyp2],
        selected_hypothesis=hyp1,
        action_plan=valid_batch_result.findings[0].action_plan,
        metric_change_summary="CTR dropped -80.0%",
        business_impact_narrative="Ad fatigue",
    )
    perf_result = BatchAnalysisResult(
        findings=[perf_finding],
        executive_summary="Summary",
        overall_data_health="HEALTHY",
        analysis_timestamp="2026-09-07T12:00:00Z",
    )

    verifier = OutputVerifier()
    res = verifier.verify(perf_result, degraded_dossier)
    assert res.is_valid is True

    healthy_ctr = MetricEvidence(
        metric_name="ctr",
        current_value=0.05,
        baseline_value=0.05,
        delta_pct=0.0,
        z_score=0.0,
        is_anomaly=False,
    )
    healthy_campaign = CampaignEvidence(
        campaign_id="cmp-perf-healthy",
        campaign_name="Perf_Campaign",
        platform="meta_ads",
        account_id="acc-201",
        country="US",
        spend=500.0,
        financial_impact_score=0.0,
        metrics={"ctr": healthy_ctr},
        data_quality_signals=(),
    )
    healthy_dossier = EvidenceDossier(
        target_date="2026-09-07",
        baseline_window="14d",
        total_anomalies_detected=0,
        total_campaigns_impacted=0,
        top_campaign_evidence=(healthy_campaign,),
    )

    res_healthy = verifier.verify(perf_result, healthy_dossier)
    assert res_healthy.is_valid is False
    assert any("PERFORMANCE diagnosis ungrounded" in err for err in res_healthy.errors)


def test_data_quality_grounding_via_conversion_collapse(
    valid_batch_result: BatchAnalysisResult,
) -> None:
    """Verify DATA_QUALITY diagnosis passes when conversions collapse to 0 with active spend."""
    collapsed_conv = MetricEvidence(
        metric_name="conversions",
        current_value=0.0,
        baseline_value=100.0,
        delta_pct=-100.0,
        z_score=-5.0,
        is_anomaly=True,
    )
    collapsed_campaign = CampaignEvidence(
        campaign_id="cmp-dq-conv",
        campaign_name="DQ_Collapse_Campaign",
        platform="google_ads",
        account_id="acc-301",
        country="US",
        spend=1000.0,
        financial_impact_score=100.0,
        metrics={"conversions": collapsed_conv},
        data_quality_signals=(),
    )
    dossier = EvidenceDossier(
        target_date="2026-09-07",
        baseline_window="14d",
        total_anomalies_detected=1,
        total_campaigns_impacted=1,
        top_campaign_evidence=(collapsed_campaign,),
    )

    hyp1 = Hypothesis(statement="Pixel issue", confidence=0.9)
    hyp2 = Hypothesis(statement="Tracking breakdown", confidence=0.1)
    dq_finding = DiagnosedFinding(
        campaign_name="DQ_Collapse_Campaign",
        platform="google_ads",
        country="US",
        issue_type="DATA_QUALITY",
        confidence_score=0.9,
        root_cause_analysis="Conversions collapsed to 0",
        competing_hypotheses=[hyp1, hyp2],
        selected_hypothesis=hyp1,
        action_plan=valid_batch_result.findings[0].action_plan,
        metric_change_summary="Conversions dropped by -100.0%",
        business_impact_narrative="Pixel failure",
    )
    dq_result = BatchAnalysisResult(
        findings=[dq_finding],
        executive_summary="Summary",
        overall_data_health="CRITICAL",
        analysis_timestamp="2026-09-07T12:00:00Z",
    )

    verifier = OutputVerifier()
    res = verifier.verify(dq_result, dossier)
    assert res.is_valid is True


def test_invalid_confidence_score_error(
    valid_batch_result: BatchAnalysisResult, valid_dossier: EvidenceDossier
) -> None:
    """Verify confidence score outside [0, 1] triggers error in GroundingVerifier."""
    finding = valid_batch_result.findings[0]

    invalid_finding = finding.model_copy(update={"confidence_score": 1.5})
    bad_result = BatchAnalysisResult(
        findings=[invalid_finding],
        executive_summary=valid_batch_result.executive_summary,
        overall_data_health=valid_batch_result.overall_data_health,
        analysis_timestamp=valid_batch_result.analysis_timestamp,
    )

    verifier = OutputVerifier()
    res = verifier.verify(bad_result, valid_dossier)
    assert res.is_valid is False
    assert any("Invalid confidence_score 1.5" in err for err in res.errors)


def test_campaign_name_hallucination(
    valid_batch_result: BatchAnalysisResult, valid_dossier: EvidenceDossier
) -> None:
    """Verify evaluation of hallucinated / unlisted campaign flags error."""
    finding = valid_batch_result.findings[0]
    fake_finding = DiagnosedFinding(
        campaign_name="Hallucinated_Campaign_999",
        platform=finding.platform,
        country=finding.country,
        issue_type=finding.issue_type,
        confidence_score=finding.confidence_score,
        root_cause_analysis=finding.root_cause_analysis,
        competing_hypotheses=finding.competing_hypotheses,
        selected_hypothesis=finding.selected_hypothesis,
        action_plan=finding.action_plan,
        metric_change_summary=finding.metric_change_summary,
        business_impact_narrative=finding.business_impact_narrative,
    )
    fake_result = BatchAnalysisResult(
        findings=[fake_finding],
        executive_summary=valid_batch_result.executive_summary,
        overall_data_health=valid_batch_result.overall_data_health,
        analysis_timestamp=valid_batch_result.analysis_timestamp,
    )

    verifier = OutputVerifier()
    res = verifier.verify(fake_result, valid_dossier)
    assert res.is_valid is False
    assert any("Hallucinated_Campaign_999" in err for err in res.errors)


def test_contract_sanity_violations(
    valid_batch_result: BatchAnalysisResult, valid_dossier: EvidenceDossier
) -> None:
    """Verify sanity checks for hypotheses count and action plan concrete steps."""
    finding = valid_batch_result.findings[0]

    empty_steps_plan = OperationalActionPlan(
        budget_action="HOLD",
        bid_action="NO_CHANGE",
        creative_action="NO_ACTION",
        tracking_action="AUDIT",
        rationale="Rationale",
        concrete_steps=[],
        expected_effect="Effect",
        risk_level="LOW",
        requires_approval=False,
    )
    invalid_finding = DiagnosedFinding(
        campaign_name=finding.campaign_name,
        platform=finding.platform,
        country=finding.country,
        issue_type=finding.issue_type,
        confidence_score=finding.confidence_score,
        root_cause_analysis=finding.root_cause_analysis,
        competing_hypotheses=[finding.selected_hypothesis],
        selected_hypothesis=finding.selected_hypothesis,
        action_plan=empty_steps_plan,
        metric_change_summary=finding.metric_change_summary,
        business_impact_narrative=finding.business_impact_narrative,
    )
    invalid_result = BatchAnalysisResult(
        findings=[invalid_finding],
        executive_summary=valid_batch_result.executive_summary,
        overall_data_health=valid_batch_result.overall_data_health,
        analysis_timestamp=valid_batch_result.analysis_timestamp,
    )

    verifier = OutputVerifier()
    res = verifier.verify(invalid_result, valid_dossier)
    assert res.is_valid is False
    assert any("must evaluate at least 2 competing hypotheses" in err for err in res.errors)
    assert any("must contain at least 1 concrete step" in err for err in res.errors)


def test_speculative_definitive_claim_rejected(
    valid_batch_result: BatchAnalysisResult, valid_dossier: EvidenceDossier
) -> None:
    """Verify definitive assertion about creative dimension is rejected."""
    finding = valid_batch_result.findings[0]
    bad_hyp = Hypothesis(
        statement="Kreatif yorgunluğu",
        supporting_evidence=["Conversions dropped by -57.14%"],
        confidence=0.9,
        missing_evidence=["Kreatif düzeyinde performans verisine ihtiyaç duyulmaktadır."],
    )
    bad_finding = finding.model_copy(
        update={
            "root_cause_analysis": "Kreatif yorgunluğu kesinleşmiştir.",
            "selected_hypothesis": bad_hyp,
        }
    )
    bad_result = valid_batch_result.model_copy(update={"findings": [bad_finding]})

    verifier = OutputVerifier()
    res = verifier.verify(bad_result, valid_dossier)
    assert res.is_valid is False
    expected_err = (
        "Unsupported definitive claim detected: 'kesinleşmiştir' "
        "asserted for unobserved dimension 'creative'"
    )
    assert any(expected_err in err for err in res.errors)


def test_properly_grounded_hypothetical_framing_passes(
    valid_batch_result: BatchAnalysisResult, valid_dossier: EvidenceDossier
) -> None:
    """Verify hypothetical framing with proper missing_evidence acknowledgment passes."""
    finding = valid_batch_result.findings[0]
    good_hyp1 = Hypothesis(
        statement="Kreatif yorgunluğu olası bir hipotezdir",
        supporting_evidence=["Conversions dropped by -57.14%"],
        confidence=0.8,
        missing_evidence=["Doğrulama için kreatif düzeyinde veriye ihtiyaç duyulmaktadır."],
    )
    good_hyp2 = Hypothesis(
        statement="Bütçe kısıtı",
        confidence=0.2,
        missing_evidence=[],
    )
    good_finding = finding.model_copy(
        update={
            "root_cause_analysis": (
                "Performans düşüşü kreatif yorgunluğundan kaynaklanıyor olabilir."
            ),
            "competing_hypotheses": [good_hyp1, good_hyp2],
            "selected_hypothesis": good_hyp1,
        }
    )
    good_result = valid_batch_result.model_copy(update={"findings": [good_finding]})

    verifier = OutputVerifier()
    res = verifier.verify(good_result, valid_dossier)
    assert res.is_valid is True
    assert len(res.errors) == 0


def test_unobserved_hypothesis_empty_missing_evidence_rejected(
    valid_batch_result: BatchAnalysisResult, valid_dossier: EvidenceDossier
) -> None:
    """Verify hypothesis referencing unobserved dimension with empty missing_evidence fails."""
    finding = valid_batch_result.findings[0]
    unack_hyp = Hypothesis(
        statement="Kreatif yorgunluğu olası bir hipotezdir",
        supporting_evidence=["Conversions dropped by -57.14%"],
        confidence=0.8,
        missing_evidence=[],
    )
    unack_finding = finding.model_copy(
        update={
            "root_cause_analysis": "Olası performans düşüş nedeni.",
            "competing_hypotheses": [unack_hyp, finding.competing_hypotheses[1]],
            "selected_hypothesis": unack_hyp,
        }
    )
    bad_result = valid_batch_result.model_copy(update={"findings": [unack_finding]})

    verifier = OutputVerifier()
    res = verifier.verify(bad_result, valid_dossier)
    assert res.is_valid is False
    expected_err = (
        "Ungrounded hypothesis: Selected hypothesis references unobserved dimension 'creative'"
    )
    assert any(expected_err in err for err in res.errors)


def test_unobserved_hypothesis_with_appropriate_missing_evidence_passes(
    valid_batch_result: BatchAnalysisResult, valid_dossier: EvidenceDossier
) -> None:
    """Verify hypothesis referencing unobserved dimension with matching missing_evidence passes."""
    finding = valid_batch_result.findings[0]
    infra_hyp = Hypothesis(
        statement="Ödeme sayfası çökmesi olası bir nedendir",
        supporting_evidence=["Conversions dropped by -57.14%"],
        confidence=0.85,
        missing_evidence=["GA4 event log ve sunucu telemetry verisi eksiktir."],
    )
    infra_finding = finding.model_copy(
        update={
            "root_cause_analysis": "Dönüşümler sıfırlandı, teknik bir sorun olabilir.",
            "competing_hypotheses": [infra_hyp, finding.competing_hypotheses[1]],
            "selected_hypothesis": infra_hyp,
        }
    )
    valid_result = valid_batch_result.model_copy(update={"findings": [infra_finding]})

    verifier = OutputVerifier()
    res = verifier.verify(valid_result, valid_dossier)
    assert res.is_valid is True
    assert len(res.errors) == 0


def test_unobserved_infrastructure_definitive_claim_rejected(
    valid_batch_result: BatchAnalysisResult, valid_dossier: EvidenceDossier
) -> None:
    """Verify definitive assertion about server infrastructure dimension is rejected."""
    finding = valid_batch_result.findings[0]
    infra_hyp = Hypothesis(
        statement="Ödeme geçidi hatası",
        confidence=0.9,
        missing_evidence=[],
    )
    infra_finding = finding.model_copy(
        update={
            "root_cause_analysis": "Ödeme sayfası çökmesi kesin olarak kanıtlanmıştır.",
            "selected_hypothesis": infra_hyp,
        }
    )
    bad_result = valid_batch_result.model_copy(update={"findings": [infra_finding]})

    verifier = OutputVerifier()
    res = verifier.verify(bad_result, valid_dossier)
    assert res.is_valid is False
    expected_claim_err = (
        "Unsupported definitive claim detected: 'kesin olarak' "
        "asserted for unobserved dimension 'infrastructure'"
    )
    expected_ground_err = (
        "Ungrounded hypothesis: Selected hypothesis references "
        "unobserved dimension 'infrastructure'"
    )
    assert any(expected_claim_err in err for err in res.errors)
    assert any(expected_ground_err in err for err in res.errors)


def test_unsupported_claim_rule_standalone(valid_batch_result: BatchAnalysisResult) -> None:
    """Verify UnsupportedClaimRule standalone execution."""
    finding = valid_batch_result.findings[0]
    bad_hyp = Hypothesis(
        statement="Creative decay is confirmed",
        confidence=0.9,
        missing_evidence=[],
    )
    bad_finding = finding.model_copy(update={"selected_hypothesis": bad_hyp})
    bad_result = valid_batch_result.model_copy(update={"findings": [bad_finding]})

    rule = UnsupportedClaimRule()
    errors, warnings = rule.verify(bad_result)
    assert len(errors) == 2
    assert any("Unsupported definitive claim detected: 'is confirmed'" in e for e in errors)
    assert any("Ungrounded hypothesis" in e for e in errors)
