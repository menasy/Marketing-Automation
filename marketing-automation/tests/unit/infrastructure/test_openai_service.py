from pathlib import Path
from unittest.mock import MagicMock

import pytest
from openai import APIConnectionError

from src.domain.enums import MetricDirection, MetricType, Platform, Severity
from src.domain.exceptions import LLMServiceError
from src.domain.models import AnomalyItem, ExecutiveBriefing
from src.infrastructure.llm.openai_service import OpenAIService
from src.infrastructure.llm.prompt_loader import PromptLoader


def test_openai_service_successful_generation() -> None:
    """Verify OpenAIService creates correct API request and maps output into ExecutiveBriefing."""
    mock_content = """# Executive Briefing

## Executive Summary
2 critical anomalies were detected across Google Ads and Meta Ads. Overall spend increased by 45%.

## Critical Anomalies
- Campaign 'Search_Brand_US' spend spiked 150% (z-score 3.2).
- Campaign 'Meta_Retargeting_DE' CPA surged 125% (z-score 2.8).

## Positive Signals
No positive anomaly signals detected in this period.

## Recommended Actions
- Review budget caps on campaign 'Search_Brand_US'.
- Pause high-cost ad sets in 'Meta_Retargeting_DE'.
"""

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = mock_content
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService(
        api_key="test-sk-12345",
        model="gpt-4o-mini",
        client=mock_client,
        seed=42,
    )

    anomalies = [
        AnomalyItem(
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
            rationale="Spend spike",
        )
    ]

    briefing = service.generate_briefing(anomalies)

    assert isinstance(briefing, ExecutiveBriefing)
    assert "2 critical anomalies were detected" in briefing.summary
    assert len(briefing.critical_findings) == 2
    assert "Search_Brand_US" in briefing.critical_findings[0]
    assert len(briefing.recommended_actions) == 2
    assert "Review budget caps" in briefing.recommended_actions[0]
    assert briefing.raw_markdown == mock_content.strip()
    assert briefing.generated_at is not None

    # Verify OpenAI client call arguments
    mock_client.chat.completions.create.assert_called_once()
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["temperature"] == 0.0
    assert kwargs["seed"] == 42
    assert kwargs["timeout"] == 30.0
    assert len(kwargs["messages"]) == 1
    assert "Search_Brand_US" in kwargs["messages"][0]["content"]


def test_openai_service_missing_api_key() -> None:
    """Verify OpenAIService raises LLMServiceError when API key is missing."""
    service = OpenAIService(api_key="", client=None)
    with pytest.raises(LLMServiceError, match="OpenAI API key is missing or empty"):
        service.generate_briefing([])


def test_openai_service_api_error_handling() -> None:
    """Verify OpenAI SDK exceptions are wrapped in LLMServiceError."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = APIConnectionError(request=MagicMock())

    service = OpenAIService(api_key="sk-test", client=mock_client)
    with pytest.raises(LLMServiceError, match="OpenAI API request failed"):
        service.generate_briefing([])


def test_openai_service_empty_response_handling() -> None:
    """Verify OpenAIService raises LLMServiceError when API returns empty content."""
    mock_response = MagicMock()
    mock_response.choices = []

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService(api_key="sk-test", client=mock_client)
    with pytest.raises(LLMServiceError, match="OpenAI response returned empty content"):
        service.generate_briefing([])


def test_openai_service_custom_prompt_loader(tmp_path: Path) -> None:
    """Verify OpenAIService accepts custom PromptLoader instance."""
    prompt_file = tmp_path / "custom.md"
    prompt_file.write_text("# Custom\n{{anomalies_json}}", encoding="utf-8")
    loader = PromptLoader(prompt_path=prompt_file)

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "## Executive Summary\nCustom briefing summary."
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService(api_key="sk-test", prompt_loader=loader, client=mock_client)
    briefing = service.generate_briefing([])

    assert "Custom briefing summary" in briefing.summary


def test_openai_service_generic_exception() -> None:
    """Verify generic unexpected exception during OpenAI call raises LLMServiceError."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("Unexpected network drop")

    service = OpenAIService(api_key="sk-test", client=mock_client)
    with pytest.raises(LLMServiceError, match="Unexpected error calling OpenAI service"):
        service.generate_briefing([])


def test_openai_service_prompt_error(tmp_path: Path) -> None:
    """Verify prompt loader error is propagated as LLMServiceError."""
    missing_file = tmp_path / "non_existent.md"
    loader = PromptLoader(prompt_path=missing_file)
    service = OpenAIService(api_key="sk-test", prompt_loader=loader)

    with pytest.raises(LLMServiceError, match="Prompt template file not found"):
        service.generate_briefing([])


def test_openai_service_summary_fallback() -> None:
    """Verify fallback summary when Executive Summary header is absent."""
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "This is a raw output without markdown headers."
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService(api_key="sk-test", client=mock_client)
    briefing = service.generate_briefing([])

    assert briefing.summary == "This is a raw output without markdown headers."


def test_openai_service_client_init_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify exception during client initialization raises LLMServiceError."""
    service = OpenAIService(api_key="sk-test", client=None)

    def mock_init(*args: object, **kwargs: object) -> None:
        raise ValueError("Invalid client parameter")

    monkeypatch.setattr("src.infrastructure.llm.openai_service.OpenAI", mock_init)
    with pytest.raises(LLMServiceError, match="Failed to initialize OpenAI client"):
        service.generate_briefing([])
