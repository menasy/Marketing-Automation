"""Use case for analyzing anomaly findings and generating executive report."""

import logging
from pathlib import Path

from src.application.ports.operational_report import IOperationalReportWriter
from src.domain.models.anomaly import AnomalyItem
from src.domain.models.operational_finding import OperationalFinding
from src.domain.services.finding_ranker import FindingRanker
from src.infrastructure.config.settings import get_settings
from src.infrastructure.reporting.operational_report import OperationalReportWriter

logger = logging.getLogger(__name__)


class AnalyzeFindingsUseCase:
    """Use case orchestrating operational finding ranking and report generation."""

    def __init__(
        self,
        report_writer: IOperationalReportWriter | None = None,
        output_path: str | Path | None = None,
    ) -> None:
        """Initialize AnalyzeFindingsUseCase with dependencies."""
        settings = get_settings()
        self._report_writer: IOperationalReportWriter = (
            report_writer if report_writer is not None else OperationalReportWriter()
        )
        self._output_path: str = (
            str(output_path)
            if output_path is not None
            else str(settings.output_dir / "top_3_findings.md")
        )

    def execute(
        self,
        anomalies: list[AnomalyItem],
        output_path: str | Path | None = None,
        max_findings: int = 3,
    ) -> list[OperationalFinding]:
        """Group anomalies by campaign, analyze root cause, rank findings, and export report.

        Args:
            anomalies: List of statistical AnomalyItem instances detected in data.
            output_path: Optional output file path override.
            max_findings: Maximum number of ranked findings to return (default 3).

        Returns:
            List of ranked OperationalFinding entities.
        """
        logger.info("Executing AnalyzeFindingsUseCase for %d anomaly items", len(anomalies))

        # 1. Domain ranking logic
        top_findings = FindingRanker.rank_findings(anomalies, max_findings=max_findings)

        # 2. Render and save report
        target_path = str(output_path) if output_path is not None else self._output_path
        self._report_writer.render_and_save(top_findings, target_path)

        logger.info(
            "Operational analysis completed. Saved %d findings to %s",
            len(top_findings),
            target_path,
        )
        return top_findings
