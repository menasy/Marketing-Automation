"""Executive briefing writer generating C-Level morning briefing in Markdown format."""

import logging
from pathlib import Path

from src.agent.schemas.reasoning import BatchAnalysisResult
from src.domain.models.evidence_dossier import EvidenceDossier
from src.infrastructure.reporting.io_utils import safe_write_text
from src.infrastructure.reporting.localization import (
    localize_health_status,
    localize_issue_type,
)

logger = logging.getLogger(__name__)


class ExecutiveBriefingWriter:
    """Renders a concise, C-Level morning executive briefing in Markdown format."""

    def render(
        self,
        result: BatchAnalysisResult,
        dossier: EvidenceDossier | None = None,
    ) -> str:
        """Render C-Level executive morning briefing into Markdown format.

        Args:
            result: BatchAnalysisResult produced by Gemini agent diagnosis.
            dossier: Optional EvidenceDossier with statistical context.

        Returns:
            Rendered Markdown content string.
        """
        health_raw = result.overall_data_health.upper()
        health_badge = localize_health_status(health_raw)

        target_date = dossier.target_date if dossier is not None else result.analysis_timestamp

        lines: list[str] = []
        lines.append("# Yönetici Brifingi: Günlük Pazarlama ve Veri İstihbaratı")
        lines.append("")
        lines.append(
            f"**Hedef Analiz Tarihi:** `{target_date}` | "
            f"**Veri Sağlığı Durumu:** **{health_badge}** | "
            f"**Çalıştırma Zamanı:** `{result.analysis_timestamp}`"
        )
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Yönetici Özet Narratifi")
        lines.append("")
        lines.append(result.executive_summary)
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Portföy Etki Özeti")
        lines.append("")

        if not result.findings:
            lines.append(
                "Bu analiz döneminde kritik kampanya anomalisi veya bulgu teşhis edilmedi."
            )
        else:
            table_header = (
                "| Kampanya | Platform | Ülke | Teşhis Sınıfı | Güven "
                "| Birincil Gerekçe / Kök Neden |"
            )
            lines.append(table_header)
            lines.append("|---|---|---|---|---|---|")
            for finding in result.findings:
                issue_badge = localize_issue_type(finding.issue_type)
                plat = finding.platform.upper()
                country = finding.country.upper()
                conf_pct = f"{finding.confidence_score * 100:.0f}%"

                # Truncate rationale for clean table layout
                rationale_text = finding.action_plan.rationale
                if len(rationale_text) > 90:
                    rationale_text = rationale_text[:87] + "..."

                lines.append(
                    f"| `{finding.campaign_name}` | `{plat}` | `{country}` | "
                    f"**{issue_badge}** | `{conf_pct}` | {rationale_text} |"
                )

        lines.append("")
        return "\n".join(lines)

    def render_and_save(
        self,
        result: BatchAnalysisResult,
        output_path: str | Path,
        dossier: EvidenceDossier | None = None,
    ) -> str:
        """Render executive briefing and write to output_path.

        Args:
            result: BatchAnalysisResult instance.
            output_path: Destination file path for sample_briefing.md.
            dossier: Optional EvidenceDossier instance.

        Returns:
            Written Markdown string content.
        """
        content = self.render(result, dossier=dossier)
        target_path = safe_write_text(output_path, content, encoding="utf-8")

        logger.info("Executive briefing successfully written to %s", target_path)
        return content
