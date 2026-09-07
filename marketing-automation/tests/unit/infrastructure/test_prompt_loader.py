from pathlib import Path

import pytest

from src.domain.enums import MetricDirection, MetricType, Platform, Severity
from src.domain.exceptions import LLMServiceError
from src.domain.models import AnomalyItem
from src.infrastructure.llm.prompt_loader import PromptLoader


def test_prompt_loader_default_path() -> None:
    """Verify PromptLoader defaults to project prompts directory."""
    loader = PromptLoader()
    assert loader.prompt_path.name == "executive_briefing.md"
    assert loader.prompt_path.is_file()


def test_prompt_loader_custom_path(tmp_path: Path) -> None:
    """Verify PromptLoader accepts and reads a custom file path."""
    custom_file = tmp_path / "custom_prompt.md"
    custom_file.write_text("Hello {{anomalies_json}}!", encoding="utf-8")

    loader = PromptLoader(prompt_path=custom_file)
    assert loader.prompt_path == custom_file
    rendered = loader.render_prompt(anomalies=[])
    assert "Hello []!" in rendered


def test_prompt_loader_missing_file(tmp_path: Path) -> None:
    """Verify PromptLoader raises LLMServiceError when file does not exist."""
    missing_file = tmp_path / "non_existent.md"
    loader = PromptLoader(prompt_path=missing_file)

    with pytest.raises(LLMServiceError, match="Prompt template file not found"):
        loader.load_raw_template()


def test_prompt_loader_missing_placeholder(tmp_path: Path) -> None:
    """Verify PromptLoader raises LLMServiceError when placeholder is missing."""
    bad_file = tmp_path / "bad_prompt.md"
    bad_file.write_text("No placeholder here", encoding="utf-8")

    loader = PromptLoader(prompt_path=bad_file)
    with pytest.raises(LLMServiceError, match="missing mandatory '{{anomalies_json}}' placeholder"):
        loader.render_prompt(anomalies=[])


def test_prompt_loader_render_with_anomaly_items() -> None:
    """Verify prompt rendering with a list of AnomalyItem domain objects."""
    loader = PromptLoader()
    anomaly = AnomalyItem(
        campaign_name="Search_Brand_US",
        platform=Platform.GOOGLE_ADS,
        country="US",
        metric=MetricType.SPEND,
        current_value=500.0,
        baseline_value=200.0,
        change_rate=1.5,
        z_score=3.2,
        severity=Severity.CRITICAL,
        direction=MetricDirection.NEUTRAL,
        detection_method="z_score",
        rationale="Spend increased 150%",
    )

    rendered = loader.render_prompt(anomalies=[anomaly])

    assert "Senior Performance Marketing Lead" in rendered
    assert "Search_Brand_US" in rendered
    assert "google_ads" in rendered
    assert "spend" in rendered
    assert "500.0" in rendered
    assert "{{anomalies_json}}" not in rendered


def test_prompt_loader_format_anomalies_types() -> None:
    """Verify formatting anomalies string, dict list, and list of items."""
    loader = PromptLoader()

    # Raw string
    assert loader.format_anomalies_json("[1, 2, 3]") == "[1, 2, 3]"

    # Dict list
    dict_payload = [{"campaign": "Test", "spend": 100}]
    formatted_json = loader.format_anomalies_json(dict_payload)
    assert '"campaign": "Test"' in formatted_json


def test_prompt_loader_unsupported_type() -> None:
    """Verify unsupported anomalies type raises LLMServiceError."""
    loader = PromptLoader()
    with pytest.raises(LLMServiceError, match="Unsupported anomalies format"):
        loader.format_anomalies_json(12345)  # type: ignore[arg-type]


def test_prompt_loader_read_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify I/O read errors raise LLMServiceError."""
    test_file = tmp_path / "prompt.md"
    test_file.write_text("content", encoding="utf-8")
    loader = PromptLoader(prompt_path=test_file)

    def mock_read_text(*args: object, **kwargs: object) -> str:
        raise OSError("Permission denied")

    monkeypatch.setattr(Path, "read_text", mock_read_text)
    with pytest.raises(LLMServiceError, match="Failed to read prompt template file"):
        loader.load_raw_template()


def test_prompt_loader_encoder_fallback() -> None:
    """Verify custom encoder falls back for non-enum non-dataclass non-standard types."""
    loader = PromptLoader()

    class CustomObject:
        pass

    with pytest.raises(TypeError):
        loader.format_anomalies_json([CustomObject()])  # type: ignore[arg-type]
