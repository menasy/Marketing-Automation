"""Operational findings Markdown report generator implementing IOperationalReportWriter."""

import logging
from pathlib import Path

from src.agent.schemas.reasoning import BatchAnalysisResult, DiagnosedFinding
from src.application.ports.operational_report import IOperationalReportWriter
from src.domain.models.operational_finding import OperationalFinding
from src.infrastructure.reporting.io_utils import safe_write_text
from src.infrastructure.reporting.localization import (
    localize_action_label,
    localize_issue_type,
    localize_severity,
)

logger = logging.getLogger(__name__)


class TopFindingsReportWriter(IOperationalReportWriter):
    """Renders top operational findings into a high-impact executive Markdown report."""

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
        target_path = safe_write_text(output_path, content, encoding="utf-8")

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
                "# Operasyonel Yönetici Raporu: En Kritik 3 Bulgu\n\n"
                "## Özet\n"
                "Herhangi bir kritik operasyonel anomali veya veri kalitesi sorunu "
                "tespit edilmedi.\n"
            )

        lines: list[str] = []
        lines.append("# Operasyonel Yönetici Raporu: En Kritik 3 Bulgu\n")
        lines.append(
            "**Yönetici Özeti:** Çoklu metrik anomalilerin sistematik operasyonel teşhisi, "
            "kök neden izolasyonu ve kanıta dayalı aksiyon adımları.\n"
        )

        # Overview Summary Table
        lines.append("### Özet Matrisi\n")
        table_hdr = (
            "| Kampanya | Platform | Ülke | Teşhis Sınıfı | Güven | Birincil Metrik Değişimi |"
        )
        lines.append(table_hdr)
        lines.append("|---|---|---|---|---|---|")

        for f in finding_items:
            if isinstance(f, DiagnosedFinding):
                plat = f.platform.upper()
                country = f.country.upper()
                issue_badge = localize_issue_type(f.issue_type)
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
                issue_badge = localize_issue_type(issue_val)
                conf_str = f"Skor: {f.score:.1f}"
                delta_str = f.metric_change

            lines.append(
                f"| `{f.campaign_name}` | `{plat}` | `{country}` | **{issue_badge}** | "
                f"`{conf_str}` | `{delta_str}` |"
            )
        lines.append("\n---\n")

        # Detailed Findings Section (Addressing Case Study Questions 1 & 2 explicitly)
        lines.append("## Detaylı Operasyonel Analiz ve Aksiyon Çerçevesi\n")

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
        issue_badge = localize_issue_type(f.issue_type)
        conf_pct = f"{f.confidence_score * 100:.0f}%"

        lines.append(f"## Bulgu {idx}: {f.campaign_name} ({plat} - {country})")
        lines.append(
            f"**Platform:** `{plat}` | **Ülke:** `{country}` | "
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

        budget_label = localize_action_label(plan.budget_action)
        bid_label = localize_action_label(plan.bid_action)
        creative_label = localize_action_label(plan.creative_action)
        tracking_label = localize_action_label(plan.tracking_action)

        lines.append(
            "**Operasyonel Aksiyon Planı:**\n"
            f"- **Bütçe Aksiyonu:** `{budget_label}`\n"
            f"- **Teklif Aksiyonu:** `{bid_label}`\n"
            f"- **Kreatif Aksiyonu:** `{creative_label}`\n"
            f"- **Takip Aksiyonu:** `{tracking_label}`\n"
        )
        lines.append(f"**Aksiyon Gerekçesi:**\n{plan.rationale}\n")

        if plan.concrete_steps:
            lines.append("**Somut Operasyonel Adımlar:**")
            for step_idx, step in enumerate(plan.concrete_steps, start=1):
                lines.append(f"{step_idx}. {step}")
            lines.append("")

        risk_label = localize_severity(plan.risk_level)
        lines.append(
            f"**Beklenen Etki:** {plan.expected_effect} | **Risk Seviyesi:** `{risk_label}`\n"
        )
        lines.append("---\n")

    def _render_legacy_finding(self, idx: int, f: OperationalFinding, lines: list[str]) -> None:
        """Render legacy OperationalFinding entity without hardcoded decision trees."""
        plat = f.platform.value.upper() if hasattr(f.platform, "value") else str(f.platform).upper()
        country = f.country.upper()
        issue_val = f.issue_type.value if hasattr(f.issue_type, "value") else str(f.issue_type)
        issue_badge = localize_issue_type(issue_val)
        sev_raw = (
            f.severity.value.upper() if hasattr(f.severity, "value") else str(f.severity).upper()
        )
        sev_label = localize_severity(sev_raw)

        lines.append(f"## Bulgu {idx}: {f.campaign_name} ({plat} - {country})")
        lines.append(
            f"**Önem Derecesi:** `{sev_label}` | **Teşhis Sınıfı:** **{issue_badge}** | "
            f"**Skor:** `{f.score:.1f}`\n"
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

        budget_label = localize_action_label(f.budget_action) if f.budget_action else "—"
        bid_label = localize_action_label(f.bid_action) if f.bid_action else "—"
        creative_label = localize_action_label(f.creative_action) if f.creative_action else "—"
        tracking_label = localize_action_label(f.tracking_action) if f.tracking_action else "—"

        lines.append(
            "**Operasyonel Aksiyon Planı:**\n"
            f"- **Bütçe Aksiyonu:** `{budget_label}`\n"
            f"- **Teklif Aksiyonu:** `{bid_label}`\n"
            f"- **Kreatif Aksiyonu:** `{creative_label}`\n"
            f"- **Takip Aksiyonu:** `{tracking_label}`\n"
        )
        if f.operational_action:
            lines.append(f"**Genel Aksiyon:** {f.operational_action}\n")
        lines.append("---\n")

    @staticmethod
    def to_finding_dict(finding: OperationalFinding | DiagnosedFinding) -> dict[str, str]:
        """Serialize a finding into dictionary format for PipelineResult.top_3_findings."""
        if isinstance(finding, DiagnosedFinding):
            issue_label = localize_issue_type(finding.issue_type)
            # Strip brackets from issue label for dict value
            clean_issue = issue_label.strip("[]")

            return {
                "campaign_name": finding.campaign_name,
                "platform": finding.platform.upper(),
                "country": finding.country.upper(),
                "metric_change": finding.metric_change_summary,
                "issue_type": clean_issue,
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

        issue_label = localize_issue_type(issue_type_val)
        clean_issue = issue_label.strip("[]")

        return {
            "campaign_name": finding.campaign_name,
            "platform": platform_val,
            "country": finding.country,
            "metric_change": finding.metric_change,
            "issue_type": clean_issue,
            "operational_action": finding.operational_action,
            "severity": severity_val,
            "score": str(round(finding.score, 1)),
        }


# Alias for backward compatibility
OperationalReportWriter = TopFindingsReportWriter
