import re
from dataclasses import is_dataclass
from enum import Enum
from typing import Any

from src.domain.exceptions import LLMValidationError
from src.domain.models.anomaly import AnomalyItem


class OutputValidator:
    """Deterministic post-validation guardrail cross-examining LLM briefings against source data."""

    # Regex patterns for extracting quoted campaign names and numeric figures
    _CAMPAIGN_SINGLE_QUOTE_PATTERN = re.compile(r"'([^']+)'")
    _CAMPAIGN_DOUBLE_QUOTE_PATTERN = re.compile(r'"([^"]+)"')
    _PERCENTAGE_PATTERN = re.compile(r"([+-]?\d+(?:\.\d+)?%)")
    _NUMERIC_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\b")

    # Known general keywords and headers to exclude from campaign verification
    _EXCLUDED_STRINGS = {
        "Executive Briefing",
        "Executive Summary",
        "Critical Anomalies",
        "Positive Signals",
        "Recommended Actions",
        "Google Ads",
        "Meta Ads",
        "google_ads",
        "meta_ads",
        "anomalies.json",
        "anomalies",
        "z_score",
        "rolling_zscore",
        "system",
        "user",
    }

    def _extract_anomaly_dicts(
        self, anomalies: list[AnomalyItem] | list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Normalizes list of AnomalyItem dataclasses or dicts into standard dictionary items."""
        items: list[dict[str, Any]] = []
        for a in anomalies:
            if isinstance(a, dict):
                items.append(a)
            elif is_dataclass(a) and not isinstance(a, type):
                items.append(
                    {
                        "campaign": getattr(a, "campaign_name", ""),
                        "platform": getattr(a, "platform", ""),
                        "country": getattr(a, "country", ""),
                        "metric": getattr(a, "metric", ""),
                        "current_value": getattr(a, "current_value", 0.0),
                        "baseline_value": getattr(a, "baseline_value", 0.0),
                        "change_rate": getattr(a, "change_rate", 0.0),
                        "z_score": getattr(a, "z_score", 0.0),
                        "severity": getattr(a, "severity", ""),
                        "rationale": getattr(a, "rationale", ""),
                    }
                )
        return items

    def validate_campaigns(
        self, raw_markdown: str, anomaly_dicts: list[dict[str, Any]]
    ) -> list[str]:
        """Verifies that all campaign names quoted in briefing exist in source data."""
        discrepancies: list[str] = []
        valid_campaigns = {
            str(item.get("campaign", "")).strip() for item in anomaly_dicts if item.get("campaign")
        }

        # Find all single-quoted and double-quoted strings
        quoted_matches = set(self._CAMPAIGN_SINGLE_QUOTE_PATTERN.findall(raw_markdown))
        quoted_matches.update(self._CAMPAIGN_DOUBLE_QUOTE_PATTERN.findall(raw_markdown))

        for candidate in quoted_matches:
            candidate_clean = candidate.strip()
            if not candidate_clean or candidate_clean in self._EXCLUDED_STRINGS:
                continue

            # If candidate resembles a campaign string and is not in valid campaigns list
            if candidate_clean not in valid_campaigns:
                # Check if candidate is part of a valid campaign name or vice versa
                matching = any(
                    candidate_clean in v_camp or v_camp in candidate_clean
                    for v_camp in valid_campaigns
                )
                if not matching:
                    discrepancies.append(
                        f"Hallucinated or unverified campaign name: '{candidate_clean}'"
                    )

        return discrepancies

    def validate_metrics(self, raw_markdown: str, anomaly_dicts: list[dict[str, Any]]) -> list[str]:
        """Verifies that metric names referenced in findings exist in source data."""
        discrepancies: list[str] = []
        valid_metrics: set[str] = set()

        for item in anomaly_dicts:
            m = item.get("metric", "")
            if isinstance(m, Enum):
                valid_metrics.add(m.value.lower())
            elif m:
                valid_metrics.add(str(m).lower())

        # Also allow standard derived metrics if in dataset
        valid_metrics.update(
            {"spend", "impressions", "clicks", "conversions", "cpa", "roas", "ctr", "cpc", "cpm"}
        )

        # Check lines under Critical Anomalies or Positive Signals
        lines = raw_markdown.splitlines()
        in_findings = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                header = stripped.lstrip("#").strip().lower()
                in_findings = "critical" in header or "positive" in header
                continue

            if in_findings and (stripped.startswith("- ") or stripped.startswith("* ")):
                # Extract potential metric tokens (e.g., CPA, ROAS, Conversions)
                tokens = [t.strip(",.:()").lower() for t in stripped.split()]
                for metric_keyword in ["cpa", "roas", "ctr", "cpc", "cpm", "conversions", "spend"]:
                    if metric_keyword in tokens and metric_keyword not in valid_metrics:
                        discrepancies.append(
                            f"Metric '{metric_keyword.upper()}' mentioned in finding line "
                            f"but not present in anomalies data: '{stripped}'"
                        )

        return discrepancies

    def validate_numerics(
        self, raw_markdown: str, anomaly_dicts: list[dict[str, Any]]
    ) -> list[str]:
        """Verifies that percentages and numeric metrics mentioned match source anomalies."""
        discrepancies: list[str] = []
        if not anomaly_dicts:
            return discrepancies

        # Collect valid numeric representations from anomaly dicts
        valid_numbers: set[float] = set()
        valid_percentages: set[str] = set()

        # Always include total anomalies count
        valid_numbers.add(float(len(anomaly_dicts)))

        for item in anomaly_dicts:
            curr = float(item.get("current_value", 0.0))
            base = float(item.get("baseline_value", 0.0))
            change = float(item.get("change_rate", 0.0))
            z_val = float(item.get("z_score", 0.0))

            valid_numbers.add(round(curr, 2))
            valid_numbers.add(round(curr, 1))
            valid_numbers.add(round(curr, 0))
            valid_numbers.add(round(base, 2))
            valid_numbers.add(round(base, 1))
            valid_numbers.add(round(base, 0))
            valid_numbers.add(round(z_val, 2))
            valid_numbers.add(round(z_val, 1))

            # Percentage representations (e.g. +188.2%, 188.2%, +188%, 188%)
            pct_val = change * 100.0
            for val in [pct_val, abs(pct_val)]:
                valid_percentages.add(f"{val:.1f}%")
                valid_percentages.add(f"+{val:.1f}%")
                valid_percentages.add(f"-{val:.1f}%")
                valid_percentages.add(f"{val:.0f}%")
                valid_percentages.add(f"+{val:.0f}%")
                valid_percentages.add(f"-{val:.0f}%")

        # Extract percentages from markdown findings
        lines = raw_markdown.splitlines()
        for line in lines:
            stripped = line.strip()
            if not (stripped.startswith("- ") or stripped.startswith("* ")):
                continue

            percentages = self._PERCENTAGE_PATTERN.findall(stripped)
            for pct in percentages:
                clean_pct = pct.strip()
                # Check if pct matches any valid percentage format or close approximation
                pct_num = float(clean_pct.rstrip("%").lstrip("+-"))
                is_valid = any(
                    abs(pct_num - float(v.rstrip("%").lstrip("+-"))) < 1.5
                    for v in valid_percentages
                )
                if not is_valid:
                    discrepancies.append(
                        f"Unverified or hallucinated percentage figure '{clean_pct}' "
                        f"in line: '{stripped}'"
                    )

        return discrepancies

    def validate(
        self,
        raw_markdown: str,
        anomalies: list[AnomalyItem] | list[dict[str, Any]],
        strict: bool = False,
    ) -> tuple[bool, list[str], str]:
        """Cross-examines LLM-generated markdown against source anomalies list.

        Args:
            raw_markdown: Raw markdown briefing text generated by LLM.
            anomalies: Source AnomalyItem entities or dicts.
            strict: If True, raises LLMValidationError on discrepancy.
                If False, prepends warning banner.

        Returns:
            Tuple of (is_valid: bool, discrepancies: list[str], output_markdown: str).

        Raises:
            LLMValidationError: If strict is True and discrepancies are found.
        """
        anomaly_dicts = self._extract_anomaly_dicts(anomalies)

        discrepancies: list[str] = []
        discrepancies.extend(self.validate_campaigns(raw_markdown, anomaly_dicts))
        discrepancies.extend(self.validate_metrics(raw_markdown, anomaly_dicts))
        discrepancies.extend(self.validate_numerics(raw_markdown, anomaly_dicts))

        if not discrepancies:
            return True, [], raw_markdown

        if strict:
            disc_str = "\n- ".join(discrepancies)
            err_msg = f"LLM briefing failed deterministic validation:\n- {disc_str}"
            raise LLMValidationError(err_msg)

        # Prepend warning banner if non-strict
        banner_lines = [
            "> ⚠️ **WARNING: DATA DISCREPANCY DETECTED IN BRIEFING**",
            "> The following statements could not be verified against source anomalies data:",
        ]
        for disc in discrepancies:
            banner_lines.append(f"> - {disc}")
        banner_lines.append("\n")

        warning_banner = "\n".join(banner_lines)
        guarded_markdown = warning_banner + raw_markdown

        return False, discrepancies, guarded_markdown
