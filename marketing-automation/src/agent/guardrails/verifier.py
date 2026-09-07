"""Deterministic verification and guardrail layer for auditing AI Agent outputs."""

import re
from dataclasses import dataclass, field

from src.agent.schemas.reasoning import BatchAnalysisResult
from src.domain.models.evidence_dossier import CampaignEvidence, EvidenceDossier


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Result of deterministic verification auditing BatchAnalysisResult against EvidenceDossier."""

    is_valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)


class NumericVerifier:
    """Deterministic verifier for numeric grounding and percentage tolerance auditing."""

    PERCENTAGE_PATTERN: re.Pattern[str] = re.compile(
        r"(?:%[+-]?\d+(?:\.\d+)?|[+-]?\d+(?:\.\d+)?\s*%)"
    )
    CURRENCY_PATTERN: re.Pattern[str] = re.compile(
        r"(?:[+-]?\$\s*\d+(?:,\d{3})*(?:\.\d+)?|[+-]?\d+(?:,\d{3})*(?:\.\d+)?\s*\$)"
    )
    DECIMAL_PATTERN: re.Pattern[str] = re.compile(
        r"(?<![\d\w.-])[+-]?\d+\.\d+(?![\d\w.-])|(?<![\d\w.-])[+-]\d+(?![\d\w.-])"
    )

    def __init__(self, tolerance: float = 1.0) -> None:
        """Initialize NumericVerifier with absolute tolerance for rounding differences.

        Args:
            tolerance: Absolute percentage/numerical tolerance (default: 1.0 for +-1.0%).
        """
        self._tolerance = tolerance

    def verify(
        self, result: BatchAnalysisResult, dossier: EvidenceDossier
    ) -> tuple[list[str], list[str]]:
        """Extract and compare cited numbers, percentages, and currencies against evidence.

        Returns:
            Tuple of (errors, warnings).
        """
        errors: list[str] = []
        warnings: list[str] = []

        campaign_map: dict[str, CampaignEvidence] = {
            ce.campaign_name: ce for ce in dossier.top_campaign_evidence
        }

        for finding in result.findings:
            ce = campaign_map.get(finding.campaign_name)
            if ce is None:
                continue  # Campaign identity handled by GroundingVerifier

            narrative_texts = [
                finding.metric_change_summary,
                finding.business_impact_narrative,
                finding.root_cause_analysis,
                finding.selected_hypothesis.statement,
            ]
            combined_text = " ".join(narrative_texts)

            percentages = self._extract_percentages(combined_text)
            currencies = self._extract_currencies(combined_text)

            clean_text = self.CURRENCY_PATTERN.sub(
                "", self.PERCENTAGE_PATTERN.sub("", combined_text)
            )
            plain_numbers = self._extract_plain_numbers(clean_text)

            dossier_percentages = self._get_dossier_percentages(ce)
            dossier_currencies = self._get_dossier_currencies(ce)
            dossier_all_values = self._get_dossier_all_values(ce)

            # Audit percentages
            for pct in percentages:
                if not any(
                    abs(pct - dossier_pct) <= self._tolerance for dossier_pct in dossier_percentages
                ):
                    errors.append(
                        f"Numeric hallucination in campaign '{finding.campaign_name}': "
                        f"cited percentage {pct}% does not match any evidence metric."
                    )

            # Audit currencies
            for curr in currencies:
                if not any(
                    abs(curr - dossier_val) <= self._tolerance for dossier_val in dossier_currencies
                ):
                    errors.append(
                        f"Numeric hallucination in campaign '{finding.campaign_name}': "
                        f"cited currency figure ${curr} does not match any evidence metric."
                    )

            # Audit plain decimal/signed numbers
            for num in plain_numbers:
                if not any(
                    abs(num - dossier_val) <= self._tolerance for dossier_val in dossier_all_values
                ):
                    errors.append(
                        f"Numeric hallucination in campaign '{finding.campaign_name}': "
                        f"cited numeric value {num} does not match any evidence metric."
                    )

        return errors, warnings

    def _extract_percentages(self, text: str) -> list[float]:
        results: list[float] = []
        for match in self.PERCENTAGE_PATTERN.finditer(text):
            raw = match.group(0).replace("%", "").replace(" ", "").replace("+", "")
            try:
                results.append(float(raw))
            except ValueError:
                pass
        return results

    def _extract_currencies(self, text: str) -> list[float]:
        results: list[float] = []
        for match in self.CURRENCY_PATTERN.finditer(text):
            raw = match.group(0).replace("$", "").replace(",", "").replace(" ", "").replace("+", "")
            try:
                results.append(float(raw))
            except ValueError:
                pass
        return results

    def _extract_plain_numbers(self, text: str) -> list[float]:
        results: list[float] = []
        for match in self.DECIMAL_PATTERN.finditer(text):
            raw = match.group(0).replace("+", "")
            try:
                results.append(float(raw))
            except ValueError:
                pass
        return results

    def _get_dossier_percentages(self, ce: CampaignEvidence) -> set[float]:
        values: set[float] = set()
        for metric in ce.metrics.values():
            if metric.delta_pct is not None:
                values.add(metric.delta_pct)
                values.add(abs(metric.delta_pct))
                values.add(metric.delta_pct * 100.0)
                values.add(abs(metric.delta_pct * 100.0))
        for sig in ce.data_quality_signals:
            if sig.delta_pct is not None:
                values.add(sig.delta_pct)
                values.add(abs(sig.delta_pct))
                values.add(sig.delta_pct * 100.0)
                values.add(abs(sig.delta_pct * 100.0))
        return values

    def _get_dossier_currencies(self, ce: CampaignEvidence) -> set[float]:
        values: set[float] = {ce.spend}
        for metric in ce.metrics.values():
            if metric.metric_name in ("spend", "cpc", "cpa", "cpm", "roas"):
                if metric.current_value is not None:
                    values.add(metric.current_value)
                if metric.baseline_value is not None:
                    values.add(metric.baseline_value)
        return values

    def _get_dossier_all_values(self, ce: CampaignEvidence) -> set[float]:
        values: set[float] = {ce.spend}
        for metric in ce.metrics.values():
            if metric.current_value is not None:
                values.add(metric.current_value)
            if metric.baseline_value is not None:
                values.add(metric.baseline_value)
            if metric.delta_pct is not None:
                values.add(metric.delta_pct)
                values.add(abs(metric.delta_pct))
                values.add(metric.delta_pct * 100.0)
                values.add(abs(metric.delta_pct * 100.0))
            if metric.z_score is not None:
                values.add(metric.z_score)
                values.add(abs(metric.z_score))
        for sig in ce.data_quality_signals:
            if sig.current_value is not None:
                values.add(sig.current_value)
            if sig.baseline_value is not None:
                values.add(sig.baseline_value)
            if sig.delta_pct is not None:
                values.add(sig.delta_pct)
                values.add(abs(sig.delta_pct))
                values.add(sig.delta_pct * 100.0)
                values.add(abs(sig.delta_pct * 100.0))
        return values


class GroundingVerifier:
    """Verifier for campaign identity, diagnostic grounding, and contract sanity."""

    def verify(
        self, result: BatchAnalysisResult, dossier: EvidenceDossier
    ) -> tuple[list[str], list[str]]:
        """Verify campaign identity, issue_type grounding, and contract sanity.

        Returns:
            Tuple of (errors, warnings).
        """
        errors: list[str] = []
        warnings: list[str] = []

        dossier_campaign_names = {ce.campaign_name for ce in dossier.top_campaign_evidence}
        campaign_map = {ce.campaign_name: ce for ce in dossier.top_campaign_evidence}

        for finding in result.findings:
            # 1. Campaign Identity Verification
            if finding.campaign_name not in dossier_campaign_names:
                errors.append(
                    f"Campaign '{finding.campaign_name}' evaluated in findings "
                    "is not listed in evidence dossier."
                )
                continue

            # 2. Contract Sanity & Metric Consistency
            if not (0.0 <= finding.confidence_score <= 1.0):
                errors.append(
                    f"Invalid confidence_score {finding.confidence_score} for campaign "
                    f"'{finding.campaign_name}': must be between 0.0 and 1.0."
                )

            if len(finding.competing_hypotheses) < 2:
                errors.append(
                    f"Campaign '{finding.campaign_name}' must evaluate at least 2 "
                    f"competing hypotheses (found {len(finding.competing_hypotheses)})."
                )

            if len(finding.action_plan.concrete_steps) < 1:
                errors.append(
                    f"Action plan for campaign '{finding.campaign_name}' must contain "
                    "at least 1 concrete step."
                )

            # 3. Diagnostic Grounding Verification
            ce = campaign_map[finding.campaign_name]
            if finding.issue_type == "DATA_QUALITY":
                has_triggered_dq_signal = any(sig.is_triggered for sig in ce.data_quality_signals)
                conv_metric = ce.metrics.get("conversions") or ce.metrics.get("conv")
                conv_collapsed = (
                    conv_metric is not None and conv_metric.current_value == 0.0 and ce.spend > 0.0
                )
                if not (has_triggered_dq_signal or conv_collapsed):
                    errors.append(
                        "DATA_QUALITY diagnosis ungrounded: no technical or tracking signals "
                        "triggered for campaign."
                    )

            elif finding.issue_type == "PERFORMANCE":
                has_degradation = self._has_performance_degradation(ce)
                if not has_degradation:
                    errors.append(
                        f"PERFORMANCE diagnosis ungrounded for campaign '{finding.campaign_name}': "
                        "no funnel metric degradation detected."
                    )

        return errors, warnings

    def _has_performance_degradation(self, ce: CampaignEvidence) -> bool:
        """Check if campaign evidence contains genuine funnel metric degradation signals."""
        for metric in ce.metrics.values():
            if metric.is_anomaly:
                return True
            if metric.z_score is not None and abs(metric.z_score) >= 1.5:
                return True
            if metric.delta_pct is not None:
                if (
                    metric.metric_name in ("ctr", "roas", "conversions", "clicks")
                    and metric.delta_pct < 0
                ):
                    return True
                if metric.metric_name in ("cpc", "cpa", "cpm", "spend") and metric.delta_pct > 0:
                    return True
        return False


class OutputVerifier:
    """Unified entry point auditing BatchAnalysisResult against EvidenceDossier."""

    def __init__(
        self,
        grounding_verifier: GroundingVerifier | None = None,
        numeric_verifier: NumericVerifier | None = None,
    ) -> None:
        """Initialize OutputVerifier with customizable sub-verifiers.

        Args:
            grounding_verifier: Optional GroundingVerifier instance.
            numeric_verifier: Optional NumericVerifier instance.
        """
        self._grounding_verifier = grounding_verifier or GroundingVerifier()
        self._numeric_verifier = numeric_verifier or NumericVerifier()

    def verify(self, result: BatchAnalysisResult, dossier: EvidenceDossier) -> VerificationResult:
        """Audit result against dossier and aggregate all validation findings.

        Args:
            result: BatchAnalysisResult generated by Agent.
            dossier: Ground-truth EvidenceDossier compiled by Python.

        Returns:
            VerificationResult containing validity flag, errors, and warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []

        g_errors, g_warnings = self._grounding_verifier.verify(result, dossier)
        errors.extend(g_errors)
        warnings.extend(g_warnings)

        n_errors, n_warnings = self._numeric_verifier.verify(result, dossier)
        errors.extend(n_errors)
        warnings.extend(n_warnings)

        return VerificationResult(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
