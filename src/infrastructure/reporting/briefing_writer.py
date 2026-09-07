"""Executive briefing writer generating C-Level morning briefing in Markdown format."""

import logging
from pathlib import Path

from src.agent.schemas.reasoning import BatchAnalysisResult
from src.domain.models.evidence_dossier import EvidenceDossier

logger = logging.getLogger(__name__)


class ExecutiveBriefingWriter:
    """Renders a concise, C-Level morning executive briefing in Markdown format."""

    _HEALTH_BADGES: dict[str, str] = {
        "HEALTHY": "🟢 HEALTHY",
        "DEGRADED": "🟡 DEGRADED",
        "CRITICAL": "🔴 CRITICAL",
    }

    _ISSUE_BADGES: dict[str, str] = {
        "DATA_QUALITY": "[VERİ / TRACKING HATASI]",
        "PERFORMANCE": "[GERÇEK PERFORMANS DÜŞÜŞÜ]",
        "MIXED": "[KARMA / BELİRSİZ]",
    }

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
        health_badge = self._HEALTH_BADGES.get(health_raw, f"[{health_raw}]")

        target_date = dossier.target_date if dossier is not None else result.analysis_timestamp

        lines: list[str] = []
        lines.append("# Executive Briefing: Daily Marketing & Data Intelligence")
        lines.append("")
        lines.append(
            f"**Target Analysis Date:** `{target_date}` | "
            f"**Data Health Status:** **{health_badge}** | "
            f"**Execution Timestamp:** `{result.analysis_timestamp}`"
        )
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Executive Summary Narrative")
        lines.append("")
        lines.append(result.executive_summary)
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Portfolio Impact Snapshot")
        lines.append("")

        if not result.findings:
            lines.append("No critical campaign anomalies or findings diagnosed in this batch run.")
        else:
            table_header = (
                "| Campaign | Platform | Country | Issue Classification | Confidence "
                "| Primary Rationale / Root Cause |"
            )
            lines.append(table_header)
            lines.append("|---|---|---|---|---|---|")
            for finding in result.findings:
                issue_raw = finding.issue_type.upper()
                issue_badge = self._ISSUE_BADGES.get(issue_raw, f"[{issue_raw}]")
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
        target_path = Path(output_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")

        logger.info("Executive briefing successfully written to %s", target_path)
        return content
