"""Deterministic fallback generator synthesizing valid BatchAnalysisResult from EvidenceDossiers."""

from datetime import UTC, datetime

from src.agent.schemas.reasoning import (
    BatchAnalysisResult,
    DiagnosedFinding,
    Hypothesis,
    OperationalActionPlan,
)
from src.domain.models.evidence_dossier import CampaignEvidence, EvidenceDossier


class DeterministicFallbackGenerator:
    """Generates unassisted factual BatchAnalysisResult directly from EvidenceDossier.

    Used as fail-safe fallback when LLM generation fails verification or raises API errors.
    """

    def generate(
        self, dossier: EvidenceDossier, errors: tuple[str, ...] = ()
    ) -> BatchAnalysisResult:
        """Convert EvidenceDossier deterministically into a valid BatchAnalysisResult.

        Args:
            dossier: Ground-truth EvidenceDossier.
            errors: Optional validation error strings triggering fallback.

        Returns:
            Valid BatchAnalysisResult containing mapped campaign findings.
        """
        has_any_dq = any(
            any(sig.is_triggered for sig in ce.data_quality_signals)
            for ce in dossier.top_campaign_evidence
        )
        overall_health = "CRITICAL" if has_any_dq else "DEGRADED"

        exec_prefix = (
            "[DETERMINISTIC FALLBACK - AGENT UNASSISTED] "
            "Doğrulama yeniden denemeden sonra başarısız oldu. "
            "Önceden hesaplanmış olgusal kanıtlar gösteriliyor."
        )
        exec_summary = (
            f"{exec_prefix} Etkilenen kampanyalar: {dossier.total_campaigns_impacted}, "
            f"Toplam anomali: {dossier.total_anomalies_detected}."
        )

        findings: list[DiagnosedFinding] = [
            self._create_finding(ce) for ce in dossier.top_campaign_evidence
        ]

        timestamp = datetime.now(UTC).isoformat()

        return BatchAnalysisResult(
            findings=findings,
            executive_summary=exec_summary,
            overall_data_health=overall_health,
            analysis_timestamp=timestamp,
        )

    def _create_finding(self, ce: CampaignEvidence) -> DiagnosedFinding:
        has_dq_signals = any(sig.is_triggered for sig in ce.data_quality_signals)
        issue_type = "DATA_QUALITY" if has_dq_signals else "PERFORMANCE"

        dq_evidence = [
            sig.factual_statement
            for sig in ce.data_quality_signals
            if sig.is_triggered and sig.factual_statement
        ]
        if not dq_evidence and has_dq_signals:
            dq_evidence = ["Veri kalitesi düzensizlik sinyali tetiklendi."]

        perf_evidence = [
            f"{name} delta: {m.delta_pct}%"
            for name, m in ce.metrics.items()
            if m.delta_pct is not None
        ]
        if not perf_evidence:
            perf_evidence = [f"Aktif harcama: ${ce.spend}."]

        hyp_a = Hypothesis(
            statement="Hipotez A: Veri Kalitesi / Tracking Sinyal Anomalisi",
            supporting_evidence=dq_evidence if has_dq_signals else [],
            contradictory_evidence=[],
            confidence=1.0 if has_dq_signals else 0.0,
            missing_evidence=[],
        )
        hyp_b = Hypothesis(
            statement="Hipotez B: Dönüşüm Hunisi Performans Düşüşü",
            supporting_evidence=perf_evidence if not has_dq_signals else [],
            contradictory_evidence=[],
            confidence=1.0 if not has_dq_signals else 0.0,
            missing_evidence=[],
        )

        selected_hyp = hyp_a if has_dq_signals else hyp_b

        action_plan = OperationalActionPlan(
            budget_action="HOLD_CURRENT_BUDGET",
            bid_action="NO_CHANGE",
            creative_action="NO_ACTION",
            tracking_action="AUDIT_TRACKING_AND_DATA_QUALITY",
            rationale=(
                "Doğrulanmamış AI çıktısı veya API hatası nedeniyle "
                "fallback modu etkinleştirildi."
            ),
            concrete_steps=[
                "Tracking altyapısını (Pixel / CAPI / GTM) denetle",
                "Temel metrikleri manuel olarak gözden geçir",
            ],
            expected_effect="Doğrulanmamış otomatik değişiklikleri önle",
            risk_level="LOW",
            requires_approval=True,
        )

        root_cause = f"'{ce.campaign_name}' kampanyası için olgusal fallback özeti: " + (
            "; ".join(dq_evidence)
            if has_dq_signals
            else f"Dönüşüm hunisi metrik değişimleri tespit edildi. Harcama: ${ce.spend}."
        )

        metric_summary = f"Spend: ${ce.spend}. " + ", ".join(
            f"{name}: delta {m.delta_pct}%"
            for name, m in ce.metrics.items()
            if m.delta_pct is not None
        )

        business_impact = (
            f"Etki skoru: {ce.financial_impact_score}. Kampanya harcaması: ${ce.spend}."
        )

        return DiagnosedFinding(
            campaign_name=ce.campaign_name,
            platform=ce.platform,
            country=ce.country,
            issue_type=issue_type,
            confidence_score=1.0,
            root_cause_analysis=root_cause,
            competing_hypotheses=[hyp_a, hyp_b],
            selected_hypothesis=selected_hyp,
            action_plan=action_plan,
            metric_change_summary=metric_summary,
            business_impact_narrative=business_impact,
        )
