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

    def __init__(self, tolerance: float = 5.0, relative_tolerance: float = 0.10) -> None:
        """Initialize NumericVerifier with absolute and relative tolerance for rounding differences.

        Args:
            tolerance: Absolute percentage/numerical tolerance (default: 5.0 for +-5.0%).
            relative_tolerance: Proportional tolerance for plain numbers (default: 0.10 = 10%).
        """
        self._tolerance = tolerance
        self._relative_tolerance = relative_tolerance

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

            # Audit plain decimal/signed numbers (proportional tolerance for rounding)
            for num in plain_numbers:
                is_grounded = any(
                    abs(num - dossier_val) <= self._tolerance
                    or (
                        abs(dossier_val) > 0.01
                        and abs(num - dossier_val) / abs(dossier_val) <= self._relative_tolerance
                    )
                    for dossier_val in dossier_all_values
                )
                if not is_grounded:
                    warnings.append(
                        f"Unverified numeric value in campaign '{finding.campaign_name}': "
                        f"cited numeric value {num} could not be matched to evidence metric "
                        f"(tolerance: ±{self._tolerance} abs / ±{self._relative_tolerance*100:.0f}% rel)."
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

    def __init__(self, unsupported_claim_rule: "UnsupportedClaimRule | None" = None) -> None:
        """Initialize GroundingVerifier with optional UnsupportedClaimRule.

        Args:
            unsupported_claim_rule: Optional UnsupportedClaimRule instance.
        """
        self._unsupported_claim_rule = unsupported_claim_rule or UnsupportedClaimRule()

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
                    warnings.append(
                        f"DATA_QUALITY diagnosis for campaign '{finding.campaign_name}' "
                        "could not be grounded to explicit tracking signals. "
                        "LLM may have inferred data quality issues from metric patterns."
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


class UnsupportedClaimRule:
    """Verifier rule for detecting speculative claims and missing evidence grounding."""

    UNOBSERVED_DIMENSIONS: dict[str, dict[str, tuple[str, ...]]] = {
        "creative": {
            "keywords": (
                "creative",
                "kreatif",
                "reklam görseli",
                "ad fatigue",
                "creative fatigue",
                "ad copy",
                "reklam metni",
            ),
            "acknowledgments": (
                "creative",
                "kreatif",
                "reklam görseli",
                "ad fatigue",
                "creative fatigue",
                "ad copy",
                "reklam metni",
                "görsel",
            ),
        },
        "infrastructure": {
            "keywords": (
                "payment gateway",
                "ödeme sayfası",
                "server crash",
                "sunucu çökmesi",
                "checkout error",
                "ödeme geçidi",
            ),
            "acknowledgments": (
                "payment gateway",
                "ödeme sayfası",
                "server crash",
                "sunucu çökmesi",
                "checkout error",
                "ödeme geçidi",
                "server",
                "sunucu",
                "checkout",
                "event log",
                "ga4",
                "landing page",
                "ödeme",
            ),
        },
    }

    DEFINITIVE_TERMS: tuple[str, ...] = (
        "kesinleşmiştir",
        "kesin olarak",
        "kanıtlanmıştır",
        "doğrulanmıştır",
        "is confirmed",
        "definitely",
        "proven to be",
        "conclusively confirmed",
    )

    def verify(
        self, result: BatchAnalysisResult, dossier: EvidenceDossier | None = None
    ) -> tuple[list[str], list[str]]:
        """Audit BatchAnalysisResult for unsupported definitive claims and ungrounded hypotheses.

        Returns:
            Tuple of (errors, warnings).
        """
        errors: list[str] = []
        warnings: list[str] = []

        for finding in result.findings:
            narrative_texts = [
                finding.root_cause_analysis,
                finding.selected_hypothesis.statement,
                finding.metric_change_summary,
            ]

            # 1. Definitive Assertion Detection
            for dim_name, dim_config in self.UNOBSERVED_DIMENSIONS.items():
                dim_keywords = dim_config["keywords"]

                for text in narrative_texts:
                    text_lower = text.lower()
                    if any(kw in text_lower for kw in dim_keywords):
                        matched_term = self._find_definitive_term(text_lower)
                        if matched_term:
                            errors.append(
                                f"Unsupported definitive claim detected: '{matched_term}' "
                                f"asserted for unobserved dimension '{dim_name}' "
                                "without underlying dimension data."
                            )
                            break  # Record one error per dimension per narrative field

            # 2. Mandatory missing_evidence Grounding Check
            selected_stmt_lower = finding.selected_hypothesis.statement.lower()
            for dim_name, dim_config in self.UNOBSERVED_DIMENSIONS.items():
                dim_keywords = dim_config["keywords"]
                dim_acks = dim_config["acknowledgments"]

                if any(kw in selected_stmt_lower for kw in dim_keywords):
                    missing_ev = finding.selected_hypothesis.missing_evidence
                    has_acknowledgment = False
                    if missing_ev:
                        for ev_item in missing_ev:
                            ev_lower = ev_item.lower()
                            if any(ack in ev_lower for ack in dim_acks):
                                has_acknowledgment = True
                                break

                    if not has_acknowledgment:
                        errors.append(
                            f"Ungrounded hypothesis: Selected hypothesis references "
                            f"unobserved dimension '{dim_name}' but 'missing_evidence' "
                            "fails to acknowledge required unobserved data."
                        )

        return errors, warnings

    def _find_definitive_term(self, text_lower: str) -> str | None:
        """Find the first definitive confirmation term present in lowercased text."""
        for term in self.DEFINITIVE_TERMS:
            if term in text_lower:
                return term
        return None


class OutputVerifier:
    """Unified entry point auditing BatchAnalysisResult against EvidenceDossier."""

    def __init__(
        self,
        grounding_verifier: GroundingVerifier | None = None,
        numeric_verifier: NumericVerifier | None = None,
        unsupported_claim_rule: UnsupportedClaimRule | None = None,
    ) -> None:
        """Initialize OutputVerifier with customizable sub-verifiers.

        Args:
            grounding_verifier: Optional GroundingVerifier instance.
            numeric_verifier: Optional NumericVerifier instance.
            unsupported_claim_rule: Optional UnsupportedClaimRule instance.
        """
        self._grounding_verifier = grounding_verifier or GroundingVerifier()
        self._numeric_verifier = numeric_verifier or NumericVerifier()
        self._unsupported_claim_rule = unsupported_claim_rule or UnsupportedClaimRule()

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

        u_errors, u_warnings = self._unsupported_claim_rule.verify(result, dossier)
        errors.extend(u_errors)
        warnings.extend(u_warnings)

        return VerificationResult(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
