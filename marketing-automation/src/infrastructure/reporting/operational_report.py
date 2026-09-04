"""Operational findings Markdown report generator implementing IOperationalReportWriter."""

import logging
from pathlib import Path

from src.application.ports.operational_report import IOperationalReportWriter
from src.domain.enums.operational import IssueType
from src.domain.models.operational_finding import OperationalFinding

logger = logging.getLogger(__name__)


class OperationalReportWriter(IOperationalReportWriter):
    """Renders top operational findings into a high-impact, 1-page executive Markdown report."""

    def render_and_save(self, findings: list[OperationalFinding], output_path: str) -> str:
        """Render operational findings to Markdown format and write to disk.

        Args:
            findings: List of top ranked OperationalFinding entities.
            output_path: Target filesystem path to save the generated Markdown report.

        Returns:
            The rendered Markdown string content.
        """
        content = self.render(findings)
        target_path = Path(output_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")

        logger.info("Operational report successfully written to %s", target_path)
        return content

    def render(self, findings: list[OperationalFinding]) -> str:
        """Format findings into 1-page executive Markdown (~400-600 words)."""
        if not findings:
            return (
                "# Executive Operational Report: Top Findings\n\n"
                "## Summary\n"
                "No critical operational anomalies or data quality issues detected.\n"
            )

        lines: list[str] = []
        lines.append("# Executive Operational Report: Top 3 Critical Findings\n")
        lines.append(
            "**Executive Summary:** Systematic operational analysis evaluating statistical "
            "anomalies across channels, isolating root causes (Data Quality vs Performance), "
            "and defining evidence-based action steps.\n"
        )

        # Overview Table
        lines.append("### Summary Matrix\n")
        lines.append(
            "| Campaign | Platform | Country | Issue Type | Severity | Score | Primary Metric |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for f in findings:
            plat = f.platform.value if hasattr(f.platform, "value") else str(f.platform)
            met = (
                f.primary_metric.value.upper()
                if hasattr(f.primary_metric, "value")
                else str(f.primary_metric).upper()
            )
            issue = (
                f.issue_type.value.upper()
                if hasattr(f.issue_type, "value")
                else str(f.issue_type).upper()
            )
            sev = (
                f.severity.value.upper()
                if hasattr(f.severity, "value")
                else str(f.severity).upper()
            )
            lines.append(
                f"| `{f.campaign_name}` | `{plat}` | `{f.country}` | **{issue}** | "
                f"`{sev}` | `{f.score:.1f}` | `{met}` |"
            )
        lines.append("\n---\n")

        # Detailed Findings Section (Addressing Case Study Questions explicitly)
        lines.append("## Detailed Operational Analysis & Action Framework\n")

        for idx, f in enumerate(findings, start=1):
            plat = f.platform.value if hasattr(f.platform, "value") else str(f.platform)
            issue_str = (
                f.issue_type.value.upper()
                if hasattr(f.issue_type, "value")
                else str(f.issue_type).upper()
            )
            sev_str = (
                f.severity.value.upper()
                if hasattr(f.severity, "value")
                else str(f.severity).upper()
            )

            lines.append(f"### Finding {idx}: {f.campaign_name} ({plat} - {f.country})")
            lines.append(
                f"**Severity:** `{sev_str}` | **Issue Classification:** `{issue_str}` | "
                f"**Score:** `{f.score:.1f}`\n"
            )
            lines.append(f"**Evidence Summary:** {f.evidence_summary}\n")

            # Question 1
            lines.append(
                "#### Soru 1: Bulgu gerçek bir performans sorununa mı işaret etmektedir, "
                "yoksa verinin kendisinden mi kaynaklanmaktadır?"
            )
            if f.issue_type == IssueType.DATA_QUALITY:
                answer_q1 = (
                    "**Yanıt (VERİ KALİTESİ / DATA_QUALITY):** Bu bulgu **veri kaynaklı "
                    f"(tracking/attribution)** bir soruna işaret etmektedir. {f.business_impact}"
                )
            elif f.issue_type == IssueType.PERFORMANCE:
                answer_q1 = (
                    "**Yanıt (GERÇEK PERFORMANS / PERFORMANCE):** Bu bulgu **gerçek bir "
                    f"performans düşüşüne** işaret etmektedir. {f.business_impact}"
                )
            else:
                answer_q1 = (
                    "**Yanıt (KARMA / MIXED):** Bu bulgu **karma/belirsiz sinyaller** "
                    f"içermektedir. {f.business_impact}"
                )
            lines.append(f"{answer_q1}\n")

            # Question 2
            lines.append(
                "#### Soru 2: Bütçe, teklif veya kreatif tarafında hangi aksiyonu alırdınız?"
            )
            lines.append(
                "**Yanıt (OPERASYONEL AKSİYON PLANI):**\n"
                f"- **Bütçe Aksiyonu (`BUDGET`):** `{f.budget_action}` — Bütçeyi gözden geçir.\n"
                f"- **Teklif Aksiyonu (`BID`):** `{f.bid_action}` — Algoritma hedefini düzenle.\n"
                f"- **Kreatif Aksiyonu (`CREATIVE`):** `{f.creative_action}` — Görsel yenile.\n"
                f"- **Takip Aksiyonu (`TRACKING`):** `{f.tracking_action}` — Piksel/GTM denetle.\n"
            )
            lines.append("---\n")

        return "\n".join(lines)

    @staticmethod
    def to_finding_dict(finding: OperationalFinding) -> dict[str, str]:
        """Serialize an OperationalFinding into the dict format for PipelineResult.top_3_findings.

        Provides a DRY mapping shared by both report rendering and pipeline result assembly.
        """
        issue_labels: dict[str, str] = {
            "data_quality": "VERİ / TRACKING HATASI",
            "performance": "GERÇEK PERFORMANS SORUNU",
            "mixed": "KARMA / BELİRSİZ",
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
            finding.platform.value
            if hasattr(finding.platform, "value")
            else str(finding.platform)
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

