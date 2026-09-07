"""Unified artifact writer service coordinating the atomic writing of case study deliverables."""

import logging
from pathlib import Path

from src.agent.schemas.reasoning import BatchAnalysisResult
from src.domain.models.evidence_dossier import EvidenceDossier
from src.infrastructure.reporting.briefing_writer import ExecutiveBriefingWriter
from src.infrastructure.reporting.json_exporter import JsonAnomalyExporter
from src.infrastructure.reporting.operational_report import TopFindingsReportWriter

logger = logging.getLogger(__name__)


class ArtifactService:
    """Unified service coordinating the atomic creation of all 3 case study deliverables."""

    def __init__(
        self,
        json_exporter: JsonAnomalyExporter | None = None,
        top_findings_writer: TopFindingsReportWriter | None = None,
        briefing_writer: ExecutiveBriefingWriter | None = None,
    ) -> None:
        """Initialize ArtifactService with dependency injection for individual writers."""
        self._json_exporter = json_exporter or JsonAnomalyExporter()
        self._top_findings_writer = top_findings_writer or TopFindingsReportWriter()
        self._briefing_writer = briefing_writer or ExecutiveBriefingWriter()

    def write_all(
        self,
        dossier: EvidenceDossier,
        result: BatchAnalysisResult,
        output_dir: Path | str,
    ) -> tuple[Path, Path, Path, Path]:
        """Atomically write all case study deliverables to target output directory.

        Deliverables generated:
        1. output/anomalies.json (Serialized statistical metrics & evidence)
        2. output/operational_assessment.md (Fulfilling Case Study Q1 & Q2)
        3. output/top_3_findings.md (Synchronized dual alias)
        4. output/sample_briefing.md (Executive morning briefing & health status)

        Args:
            dossier: Statistical EvidenceDossier compiled by Python engine.
            result: Gemini agent BatchAnalysisResult with verified diagnoses.
            output_dir: Target directory path for file outputs.

        Returns:
            Tuple of 4 Path objects: (anomalies, assessment, top_findings, briefing).
        """
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        anomalies_path = target_dir / "anomalies.json"
        operational_assessment_path = target_dir / "operational_assessment.md"
        top_findings_path = target_dir / "top_3_findings.md"
        briefing_path = target_dir / "sample_briefing.md"

        # 1. Deliverable 1: anomalies.json
        self._json_exporter.export_to_file(dossier, anomalies_path)

        # 2 & 3. Deliverables 2 & 3: operational_assessment.md & top_3_findings.md (Synchronized)
        rendered_report = self._top_findings_writer.render_and_save(
            result, operational_assessment_path
        )
        top_findings_path.write_text(rendered_report, encoding="utf-8")

        # 4. Deliverable 4: sample_briefing.md
        self._briefing_writer.render_and_save(result, briefing_path, dossier=dossier)

        logger.info(
            "ArtifactService wrote deliverables to %s:\n - %s\n - %s\n - %s\n - %s",
            target_dir,
            anomalies_path,
            operational_assessment_path,
            top_findings_path,
            briefing_path,
        )

        return (
            anomalies_path,
            operational_assessment_path,
            top_findings_path,
            briefing_path,
        )
