import logging
from datetime import UTC, datetime

from openai import OpenAI, OpenAIError

from src.application.ports.llm_service import ILLMService
from src.domain.exceptions import LLMServiceError
from src.domain.models.anomaly import AnomalyItem
from src.domain.models.briefing import ExecutiveBriefing
from src.infrastructure.config.settings import get_settings
from src.infrastructure.llm.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


def _extract_section_text(markdown: str, heading_keyword: str) -> str:
    """Extracts text content under a specified Markdown header."""
    lines = markdown.splitlines()
    capturing = False
    captured_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            header_title = stripped.lstrip("#").strip().lower()
            if capturing:
                break
            if heading_keyword.lower() in header_title:
                capturing = True
                continue
        elif capturing:
            captured_lines.append(line)

    return "\n".join(captured_lines).strip()


def _extract_bullet_points(section_text: str) -> list[str]:
    """Extracts bulleted list items from Markdown section text."""
    bullets: list[str] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            item = stripped[2:].strip()
            if item:
                bullets.append(item)
    return bullets


class OpenAIService(ILLMService):
    """OpenAI implementation of ILLMService port for evidence-grounded briefing generation."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        prompt_loader: PromptLoader | None = None,
        client: OpenAI | None = None,
        timeout: float = 30.0,
        seed: int = 42,
    ) -> None:
        """Initializes OpenAIService with configuration and optional client injection."""
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.openai_api_key
        self._model = model if model is not None else settings.openai_model
        self._prompt_loader = prompt_loader if prompt_loader is not None else PromptLoader()
        self._timeout = timeout
        self._seed = seed
        self._client = client

    def _get_client(self) -> OpenAI:
        """Lazily creates or returns OpenAI API client instance."""
        if self._client is not None:
            return self._client

        if not self._api_key:
            raise LLMServiceError(
                "OpenAI API key is missing or empty. Set OPENAI_API_KEY environment variable."
            )

        try:
            return OpenAI(api_key=self._api_key, timeout=self._timeout)
        except Exception as err:
            raise LLMServiceError(f"Failed to initialize OpenAI client: {err}") from err

    def generate_briefing(self, anomalies: list[AnomalyItem]) -> ExecutiveBriefing:
        """Generates evidence-grounded ExecutiveBriefing from detected anomalies.

        Args:
            anomalies: List of detected AnomalyItem entities.

        Returns:
            ExecutiveBriefing domain entity containing raw markdown and parsed findings.

        Raises:
            LLMServiceError: If prompt rendering, API communication, or response parsing fails.
        """
        try:
            prompt_text = self._prompt_loader.render_prompt(anomalies)
        except LLMServiceError:
            raise
        except Exception as err:
            raise LLMServiceError(f"Failed to prepare prompt context: {err}") from err

        client = self._get_client()

        logger.info(
            "Requesting executive briefing from OpenAI model %s with %d anomalies",
            self._model,
            len(anomalies),
        )

        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": prompt_text},
                ],
                temperature=0.0,
                seed=self._seed,
                timeout=self._timeout,
            )
        except OpenAIError as err:
            logger.error("OpenAI API call failed: %s", err)
            raise LLMServiceError(f"OpenAI API request failed: {err}") from err
        except Exception as err:
            logger.error("Unexpected error during LLM request: %s", err)
            raise LLMServiceError(f"Unexpected error calling OpenAI service: {err}") from err

        if not response.choices or not response.choices[0].message.content:
            raise LLMServiceError("OpenAI response returned empty content.")

        raw_markdown = response.choices[0].message.content.strip()

        # Parse sections from generated markdown
        summary_text = _extract_section_text(raw_markdown, "Executive Summary")
        if not summary_text:
            # Fallback summary if header missing
            summary_text = raw_markdown.split("\n\n")[0] if raw_markdown else "Executive Briefing"

        critical_text = _extract_section_text(raw_markdown, "Critical Anomalies")
        critical_findings = _extract_bullet_points(critical_text)

        recommended_text = _extract_section_text(raw_markdown, "Recommended Actions")
        recommended_actions = _extract_bullet_points(recommended_text)

        return ExecutiveBriefing(
            summary=summary_text,
            raw_markdown=raw_markdown,
            critical_findings=critical_findings,
            recommended_actions=recommended_actions,
            generated_at=datetime.now(UTC),
        )
