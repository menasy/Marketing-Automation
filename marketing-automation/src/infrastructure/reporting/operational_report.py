"""Operational findings Markdown report generator implementing IOperationalReportWriter."""

import logging
from pathlib import Path

from src.agent.schemas.reasoning import BatchAnalysisResult, DiagnosedFinding
from src.application.ports.operational_report import IOperationalReportWriter
from src.domain.models.operational_finding import OperationalFinding

logger = logging.getLogger(__name__)


class TopFindingsReportWriter(IOperationalReportWriter):
    """Renders top operational findings into a high-impact executive Markdown report."""

    _ISSUE_BADGES: dict[str, str] = {
        "DATA_QUALITY": "[VERİ / TRACKING HATASI]",
        "PERFORMANCE": "[GERÇEK PERFORMANS DÜŞÜŞÜ]",
        "MIXED": "[KARMA / BELİRSİZ]",
        "data_quality": "[VERİ / TRACKING HATASI]",
        "performance": "[GERÇEK PERFORMANS DÜŞÜŞÜ]",
        "mixed": "[KARMA / BELİRSİZ]",
    }

    def render_and_save(
        self,
        findings: list[DiagnosedFinding] | BatchAnalysisResult | list[OperationalFinding],
        output_path: str | Path,
    ) -> str:
        """Render operational findings to Markdown format and write to disk.

        Args:
            findings: DiagnosedFinding list, BatchAnalysisResult, or OperationalFinding list.
            output_path: Target filesystem path to save the generated Markdown report.

        Returns:
            The rendered Markdown string content.
        """
        content = self.render(findings)
        target_path = Path(output_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")

        logger.info("Top 3 findings report successfully written to %s", target_path)
        return content

    def render(
        self,
        findings: list[DiagnosedFinding] | BatchAnalysisResult | list[OperationalFinding],
    ) -> str:
        """Format findings into Markdown report constrained to top 3 findings."""
        finding_items: list[DiagnosedFinding | OperationalFinding]
        if isinstance(findings, BatchAnalysisResult):
            finding_items = [item for item in findings.findings[:3]]
        elif isinstance(findings, list):
            finding_items = [item for item in findings[:3]]
        else:
            finding_items = []

        if not finding_items:
            return (
                "# Executive Operational Report: Top 3 Critical Findings\n\n"
                "## Summary\n"
                "No critical operational anomalies or data quality issues detected.\n"
            )

        lines: list[str] = []
        lines.append("# Executive Operational Report: Top 3 Critical Findings\n")
        lines.append(
            "**Executive Overview:** Systematic operational diagnosis evaluating multi-metric "
            "anomalies, isolating root causes, and defining evidence-based action steps.\n"
        )

        # Overview Summary Table
        lines.append("### Summary Matrix\n")
        table_hdr = (
            "| Campaign | Platform | Country | Issue Classification | Confidence "
            "| Primary Metric Delta |"
        )
        lines.append(table_hdr)
        lines.append("|---|---|---|---|---|---|")

        for f in finding_items:
            if isinstance(f, DiagnosedFinding):
                plat = f.platform.upper()
                country = f.country.upper()
                issue_badge = self._ISSUE_BADGES.get(f.issue_type, f"[{f.issue_type}]")
                conf_str = f"{f.confidence_score * 100:.0f}%"
                delta_str = f.metric_change_summary
            else:
                plat = (
                    f.platform.value.upper()
                    if hasattr(f.platform, "value")
                    else str(f.platform).upper()
                )
                country = f.country.upper()
                issue_val = (
                    f.issue_type.value if hasattr(f.issue_type, "value") else str(f.issue_type)
                )
                issue_badge = self._ISSUE_BADGES.get(issue_val, f"[{issue_val.upper()}]")
                conf_str = f"Score: {f.score:.1f}"
                delta_str = f.metric_change

            lines.append(
                f"| `{f.campaign_name}` | `{plat}` | `{country}` | **{issue_badge}** | "
                f"`{conf_str}` | `{delta_str}` |"
            )
        lines.append("\n---\n")

        # Detailed Findings Section (Addressing Case Study Questions 1 & 2 explicitly)
        lines.append("## Detailed Operational Analysis & Action Framework\n")

        for idx, f in enumerate(finding_items, start=1):
            if isinstance(f, DiagnosedFinding):
                self._render_diagnosed_finding(idx, f, lines)
            else:
                self._render_legacy_finding(idx, f, lines)

        return "\n".join(lines)

    def _render_diagnosed_finding(self, idx: int, f: DiagnosedFinding, lines: list[str]) -> None:
        """Render a single DiagnosedFinding fulfilling Question 1 and Question 2."""
        plat = f.platform.upper()
        country = f.country.upper()
        issue_badge = self._ISSUE_BADGES.get(f.issue_type, f"[{f.issue_type}]")
        conf_pct = f"{f.confidence_score * 100:.0f}%"

        lines.append(f"### Finding {idx}: {f.campaign_name} ({plat} - {country})")
        lines.append(
            f"**Platform:** `{plat}` | **Country:** `{country}` | "
            f"**Teşhis Sınıfı:** **{issue_badge}** | **Güven Skoru:** `{conf_pct}`\n"
        )

        lines.append("#### Metrik ve Kanıt Özeti")
        lines.append(f"{f.metric_change_summary}\n")

        # Question 1: Diagnosis & Root Cause Analysis
        lines.append(
            "#### Soru 1: Bulgu gerçek bir performans sorununa mı işaret etmektedir, "
            "yoksa verinin kendisinden mi kaynaklanmaktadır?"
        )
        lines.append(f"**Teşhis Sınıfı:** **{issue_badge}**\n")
        lines.append(f"**Kök Neden Analizi:**\n{f.root_cause_analysis}\n")

        lines.append("**Seçilen Hipotez:**")
        lines.append(f"- **Hipotez:** {f.selected_hypothesis.statement}")
        lines.append(f"- **Güven Seviyesi:** `{f.selected_hypothesis.confidence * 100:.0f}%`")
        if f.selected_hypothesis.missing_evidence:
            missing_str = ", ".join(f.selected_hypothesis.missing_evidence)
            lines.append(f"- **Eksik Kanıt:** {missing_str}")
        lines.append("")

        lines.append(f"**İş Etkisi Analizi:**\n{f.business_impact_narrative}\n")

        # Question 2: Operational Action Plan
        lines.append("#### Soru 2: Bütçe, teklif veya kreatif tarafında hangi aksiyonu alırdınız?")
        plan = f.action_plan
        lines.append(
            "**Operasyonel Aksiyon Planı:**\n"
            f"- **Bütçe Aksiyonu (`BUDGET`):** `{plan.budget_action}`\n"
            f"- **Teklif Aksiyonu (`BID`):** `{plan.bid_action}`\n"
            f"- **Kreatif Aksiyonu (`CREATIVE`):** `{plan.creative_action}`\n"
            f"- **Takip Aksiyonu (`TRACKING`):** `{plan.tracking_action}`\n"
        )
        lines.append(f"**Aksiyon Gerekçesi (Rationale):**\n{plan.rationale}\n")

        if plan.concrete_steps:
            lines.append("**Somut Operasyonel Adımlar:**")
            for step_idx, step in enumerate(plan.concrete_steps, start=1):
                lines.append(f"{step_idx}. {step}")
            lines.append("")

        lines.append(
            f"**Beklenen Etki:** {plan.expected_effect} | **Risk Seviyesi:** `{plan.risk_level}`\n"
        )
        lines.append("---\n")

    def _render_legacy_finding(self, idx: int, f: OperationalFinding, lines: list[str]) -> None:
        """Render legacy OperationalFinding entity without hardcoded decision trees."""
        plat = f.platform.value.upper() if hasattr(f.platform, "value") else str(f.platform).upper()
        country = f.country.upper()
        issue_val = f.issue_type.value if hasattr(f.issue_type, "value") else str(f.issue_type)
        issue_badge = self._ISSUE_BADGES.get(issue_val, f"[{issue_val.upper()}]")
        sev_str = (
            f.severity.value.upper() if hasattr(f.severity, "value") else str(f.severity).upper()
        )

        lines.append(f"### Finding {idx}: {f.campaign_name} ({plat} - {country})")
        lines.append(
            f"**Severity:** `{sev_str}` | **Teşhis Sınıfı:** **{issue_badge}** | "
            f"**Score:** `{f.score:.1f}`\n"
        )
        lines.append(f"**Kanıt Özeti:** {f.evidence_summary}\n")

        # Question 1
        lines.append(
            "#### Soru 1: Bulgu gerçek bir performans sorununa mı işaret etmektedir, "
            "yoksa verinin kendisinden mi kaynaklanmaktadır?"
        )
        lines.append(f"**Teşhis:** **{issue_badge}** — {f.business_impact}\n")

        # Question 2
        lines.append("#### Soru 2: Bütçe, teklif veya kreatif tarafında hangi aksiyonu alırdınız?")
        lines.append(
            "**Operasyonel Aksiyon Planı:**\n"
            f"- **Bütçe Aksiyonu (`BUDGET`):** `{f.budget_action}`\n"
            f"- **Teklif Aksiyonu (`BID`):** `{f.bid_action}`\n"
            f"- **Kreatif Aksiyonu (`CREATIVE`):** `{f.creative_action}`\n"
            f"- **Takip Aksiyonu (`TRACKING`):** `{f.tracking_action}`\n"
        )
        if f.operational_action:
            lines.append(f"**Genel Aksiyon:** {f.operational_action}\n")
        lines.append("---\n")

    @staticmethod
    def to_finding_dict(finding: OperationalFinding | DiagnosedFinding) -> dict[str, str]:
        """Serialize a finding into dictionary format for PipelineResult.top_3_findings."""
        issue_labels: dict[str, str] = {
            "DATA_QUALITY": "VERİ / TRACKING HATASI",
            "PERFORMANCE": "GERÇEK PERFORMANS SORUNU",
            "MIXED": "KARMA / BELİRSİZ",
            "data_quality": "VERİ / TRACKING HATASI",
            "performance": "GERÇEK PERFORMANS SORUNU",
            "mixed": "KARMA / BELİRSİZ",
        }

        if isinstance(finding, DiagnosedFinding):
            return {
                "campaign_name": finding.campaign_name,
                "platform": finding.platform.upper(),
                "country": finding.country.upper(),
                "metric_change": finding.metric_change_summary,
                "issue_type": issue_labels.get(finding.issue_type, finding.issue_type.upper()),
                "operational_action": finding.action_plan.rationale,
                "severity": "HIGH",
                "score": str(round(finding.confidence_score * 100, 1)),
            }

        issue_type_val = (
            finding.issue_type.value
            if hasattr(finding.issue_type, "value")
            else str(finding.issue_type)
        )
        severity_val = (
            finding.severity.value.upper()
            if hasattr(finding.severity, "value")
            else str(finding.severity).upper()
        )
        platform_val = (
            finding.platform.value if hasattr(finding.platform, "value") else str(finding.platform)
        )
        return {
            "campaign_name": finding.campaign_name,
            "platform": platform_val,
            "country": finding.country,
            "metric_change": finding.metric_change,
            "issue_type": issue_labels.get(issue_type_val, issue_type_val.upper()),
            "operational_action": finding.operational_action,
            "severity": severity_val,
            "score": str(round(finding.score, 1)),
        }


# Alias for backward compatibility
OperationalReportWriter = TopFindingsReportWriter
