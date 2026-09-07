import logging
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from src.application.ports.llm_service import ILLMService
from src.domain.enums import Severity
from src.domain.models.anomaly import AnomalyItem
from src.domain.models.briefing import ExecutiveBriefing
from src.infrastructure.config.settings import get_settings
from src.infrastructure.llm.gemini_service import GeminiService
from src.infrastructure.llm.openai_service import OpenAIService
from src.infrastructure.llm.output_validator import OutputValidator

logger = logging.getLogger(__name__)


class GenerateBriefingUseCase:
    """Orchestrates evidence-grounded briefing generation, output validation, and export."""

    def __init__(
        self,
        llm_service: ILLMService | None = None,
        output_validator: OutputValidator | None = None,
        output_dir: Path | str | None = None,
    ) -> None:
        """Initializes GenerateBriefingUseCase with dependencies or defaults."""
        settings = get_settings()
        if llm_service is not None:
            self._llm_service = llm_service
        elif settings.llm_provider.lower() == "openai":
            self._llm_service = OpenAIService()
        else:
            self._llm_service = GeminiService()

        self._output_validator = (
            output_validator if output_validator is not None else OutputValidator()
        )
        if output_dir is None:
            self._output_dir = settings.output_dir
        else:
            self._output_dir = Path(output_dir)

    def _generate_deterministic_fallback(self, anomalies: list[AnomalyItem]) -> ExecutiveBriefing:
        """Generates a template-based briefing directly from anomaly items.

        Used when the LLM provider is unavailable or fails.
        """

        logger.info("Generating deterministic fallback briefing for %d anomalies", len(anomalies))

        if not anomalies:
            raw_markdown = """# Executive Briefing

## Executive Summary
No performance anomalies were detected during the evaluated period.

## Critical Anomalies
- No critical performance anomalies detected.

## Positive Signals
- Performance remains within standard statistical baseline boundaries.

## Recommended Actions
- Continue standard campaign monitoring and baseline tracking.
"""
            return ExecutiveBriefing(
                summary="No performance anomalies were detected during the evaluated period.",
                raw_markdown=raw_markdown,
                critical_findings=[],
                recommended_actions=["Continue standard campaign monitoring."],
                generated_at=datetime.now(UTC),
            )

        critical_items = [
            a
            for a in anomalies
            if getattr(a, "severity", None)
            in (Severity.CRITICAL, Severity.HIGH, "critical", "high")
        ]
        critical_lines: list[str] = []
        critical_findings: list[str] = []

        for a in critical_items if critical_items else anomalies[:5]:
            p_val = a.platform.value if isinstance(a.platform, Enum) else str(a.platform)
            m_val = a.metric.value.upper() if isinstance(a.metric, Enum) else str(a.metric).upper()
            finding_text = f"Campaign '{a.campaign_name}' ({p_val}): {m_val} - {a.rationale}"
            critical_lines.append(f"- {finding_text}")
            critical_findings.append(finding_text)

        summary_text = (
            f"Detected {len(anomalies)} statistical anomalies "
            f"({len(critical_items)} critical/high severity) "
            "across advertising channels during the evaluation period."
        )

        actions = [
            "Audit daily budget caps for campaigns exhibiting critical CPA spikes or ROAS drops.",
            "Inspect ad delivery settings and creative fatigue for affected ad sets.",
            "Verify tracking parameters and conversion attribution pipelines.",
        ]
        action_lines = [f"- {act}" for act in actions]

        raw_markdown = f"""# Executive Briefing (Deterministic Fallback)

## Executive Summary
{summary_text}

## Critical Anomalies
{chr(10).join(critical_lines) if critical_lines else "- No critical anomalies detected."}

## Positive Signals
- No positive anomaly signals detected in this period.

## Recommended Actions
{chr(10).join(action_lines)}
"""

        return ExecutiveBriefing(
            summary=summary_text,
            raw_markdown=raw_markdown,
            critical_findings=critical_findings,
            recommended_actions=actions,
            generated_at=datetime.now(UTC),
        )

    def execute(
        self,
        anomalies: list[AnomalyItem],
        save_path: Path | str | None = None,
        strict: bool = False,
    ) -> ExecutiveBriefing:
        """Generates, validates, and exports an executive briefing.

        Args:
            anomalies: List of detected AnomalyItem entities.
            save_path: Optional explicit file path to save the generated markdown briefing.
            strict: If True, raises LLMValidationError on validation discrepancy.

        Returns:
            Validated ExecutiveBriefing domain entity.
        """
        is_fallback = False
        briefing: ExecutiveBriefing

        try:
            briefing = self._llm_service.generate_briefing(anomalies)
        except Exception as err:
            logger.warning(
                "LLM service provider failed (%s). Falling back to deterministic briefing.",
                err,
            )
            briefing = self._generate_deterministic_fallback(anomalies)
            is_fallback = True

        # Apply OutputValidator guardrail if generated via LLM
        if not is_fallback:
            _, _, validated_markdown = self._output_validator.validate(
                raw_markdown=briefing.raw_markdown,
                anomalies=anomalies,
                strict=strict,
            )
            if validated_markdown != briefing.raw_markdown:
                briefing = ExecutiveBriefing(
                    summary=briefing.summary,
                    raw_markdown=validated_markdown,
                    critical_findings=briefing.critical_findings,
                    recommended_actions=briefing.recommended_actions,
                    generated_at=briefing.generated_at,
                )

        # Export markdown to disk
        target_path = Path(save_path) if save_path else self._output_dir / "sample_briefing.md"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(briefing.raw_markdown, encoding="utf-8")
        logger.info("Saved executive briefing to: %s", target_path)

        return briefing
