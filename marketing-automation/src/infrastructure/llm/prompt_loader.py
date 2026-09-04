import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from src.domain.exceptions import LLMServiceError
from src.domain.models.anomaly import AnomalyItem
from src.infrastructure.config.settings import get_settings


class _AnomalyJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for domain enums and dataclasses."""

    def default(self, o: Any) -> Any:
        if isinstance(o, Enum):
            return o.value
        if is_dataclass(o) and not isinstance(o, type):
            return asdict(o)
        return super().default(o)


class PromptLoader:
    """Safe filesystem loader for LLM system prompt templates with placeholder substitution."""

    def __init__(self, prompt_path: Path | str | None = None) -> None:
        """Initializes PromptLoader with a specific prompt path or defaults to settings."""
        if prompt_path is None:
            settings = get_settings()
            self._prompt_path = settings.prompts_dir / "executive_briefing.md"
        else:
            self._prompt_path = Path(prompt_path)

    @property
    def prompt_path(self) -> Path:
        """Returns the absolute path to the prompt template file."""
        return self._prompt_path

    def load_raw_template(self) -> str:
        """Reads raw template file from filesystem.

        Raises:
            LLMServiceError: If template file does not exist or cannot be read.
        """
        if not self._prompt_path.is_file():
            raise LLMServiceError(f"Prompt template file not found at: {self._prompt_path}")

        try:
            return self._prompt_path.read_text(encoding="utf-8")
        except Exception as err:
            raise LLMServiceError(
                f"Failed to read prompt template file at {self._prompt_path}: {err}"
            ) from err

    def format_anomalies_json(
        self, anomalies: list[AnomalyItem] | list[dict[str, Any]] | str
    ) -> str:
        """Formats anomalies into a clean, pretty-printed JSON string.

        Args:
            anomalies: List of AnomalyItem dataclasses, list of dicts, or pre-formatted JSON.

        Returns:
            Formatted JSON string payload.
        """
        if isinstance(anomalies, str):
            return anomalies.strip()

        if isinstance(anomalies, list):
            items_to_serialize = [
                asdict(item) if is_dataclass(item) and not isinstance(item, type) else item
                for item in anomalies
            ]
            return json.dumps(items_to_serialize, cls=_AnomalyJSONEncoder, indent=2)

        raise LLMServiceError(f"Unsupported anomalies format: {type(anomalies)}")

    def render_prompt(self, anomalies: list[AnomalyItem] | list[dict[str, Any]] | str) -> str:
        """Loads prompt template and replaces {{anomalies_json}} placeholder.

        Args:
            anomalies: Detected anomaly items to inject into prompt context.

        Returns:
            Rendered prompt string ready for LLM consumption.

        Raises:
            LLMServiceError: If template file missing or placeholder substitution fails.
        """
        template = self.load_raw_template()
        anomalies_json_str = self.format_anomalies_json(anomalies)

        if "{{anomalies_json}}" not in template:
            raise LLMServiceError(
                "Prompt template missing mandatory '{{anomalies_json}}' placeholder."
            )

        return template.replace("{{anomalies_json}}", anomalies_json_str)
