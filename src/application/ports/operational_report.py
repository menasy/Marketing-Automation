"""Abstract port for operational report rendering and file persistence."""

from typing import Protocol

from src.domain.models.operational_finding import OperationalFinding


class IOperationalReportWriter(Protocol):
    """Abstract port for rendering top operational findings to Markdown and saving to disk."""

    def render_and_save(self, findings: list[OperationalFinding], output_path: str) -> str:
        """Renders findings to Markdown format and writes to output_path.

        Args:
            findings: List of ranked OperationalFinding entities.
            output_path: Target filesystem path to save the generated Markdown report.

        Returns:
            The rendered Markdown string content.
        """
        ...
