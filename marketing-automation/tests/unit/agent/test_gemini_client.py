"""Unit tests for GeminiStructuredClient using mock google-genai SDK calls."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai import errors as genai_errors

from src.agent.exceptions import AgentExecutionError, AgentSchemaValidationError
from src.agent.runtime.gemini_client import GeminiStructuredClient
from src.agent.schemas.reasoning import BatchAnalysisResult
from src.infrastructure.config.settings import Settings

VALID_BATCH_JSON = """
{
    "findings": [
        {
            "campaign_name": "Test_Campaign",
            "platform": "google_ads",
            "country": "US",
            "issue_type": "DATA_QUALITY",
            "confidence_score": 0.95,
            "root_cause_analysis": "Root cause explanation.",
            "competing_hypotheses": [
                {
                    "statement": "Tracking break",
                    "supporting_evidence": ["Zero conversions"],
                    "contradictory_evidence": [],
                    "confidence": 0.95,
                    "missing_evidence": []
                }
            ],
            "selected_hypothesis": {
                "statement": "Tracking break",
                "supporting_evidence": ["Zero conversions"],
                "contradictory_evidence": [],
                "confidence": 0.95,
                "missing_evidence": []
            },
            "action_plan": {
                "budget_action": "HOLD_CURRENT_BUDGET",
                "bid_action": "NO_CHANGE",
                "creative_action": "NO_ACTION",
                "tracking_action": "AUDIT_PIXEL",
                "rationale": "Data quality issue.",
                "concrete_steps": ["Verify pixel"],
                "expected_effect": "Fix tracking",
                "risk_level": "LOW",
                "requires_approval": false
            },
            "metric_change_summary": "Conversions: 50 → 0 (-100%)",
            "business_impact_narrative": "Impact narrative"
        }
    ],
    "executive_summary": "Executive briefing text in Turkish.",
    "overall_data_health": "DEGRADED",
    "analysis_timestamp": "2026-09-07T12:00:00Z"
}
"""


@pytest.fixture
def mock_settings() -> Settings:
    """Fixture providing test settings."""
    return Settings(
        gemini_api_key="test-mock-api-key-12345",
        gemini_model="gemini-2.5-flash",
    )


@pytest.mark.asyncio
async def test_generate_structured_analysis_success(mock_settings: Settings) -> None:
    """Verify generate_structured_analysis parses valid JSON into BatchAnalysisResult."""
    mock_response = MagicMock()
    mock_response.text = VALID_BATCH_JSON

    with patch("google.genai.Client") as mock_genai_cls:
        mock_client_inst = MagicMock()
        mock_aio_models = MagicMock()
        mock_aio_models.generate_content = AsyncMock(return_value=mock_response)
        mock_client_inst.aio.models = mock_aio_models
        mock_genai_cls.return_value = mock_client_inst

        client = GeminiStructuredClient(settings=mock_settings)
        result = await client.generate_structured_analysis(
            system_instruction="You are an expert strategist.",
            user_prompt="Analyze dossier",
        )

        assert isinstance(result, BatchAnalysisResult)
        assert len(result.findings) == 1
        assert result.findings[0].campaign_name == "Test_Campaign"
        assert result.overall_data_health == "DEGRADED"

        # Verify call parameters
        mock_aio_models.generate_content.assert_called_once()
        _, kwargs = mock_aio_models.generate_content.call_args
        assert kwargs["model"] == "gemini-2.5-flash"
        assert kwargs["contents"] == "Analyze dossier"

        config = kwargs["config"]
        assert config.temperature == 0.0
        assert config.response_mime_type == "application/json"
        assert config.response_schema == BatchAnalysisResult


@pytest.mark.asyncio
async def test_generate_structured_analysis_api_error(mock_settings: Settings) -> None:
    """Verify Gemini API errors raise AgentExecutionError."""
    with patch("google.genai.Client") as mock_genai_cls:
        mock_client_inst = MagicMock()
        mock_aio_models = MagicMock()
        mock_aio_models.generate_content = AsyncMock(
            side_effect=genai_errors.APIError(
                code=429,
                response_json={"message": "Quota exhausted"},
                response=None,
            )
        )
        mock_client_inst.aio.models = mock_aio_models
        mock_genai_cls.return_value = mock_client_inst

        client = GeminiStructuredClient(settings=mock_settings)
        with pytest.raises(AgentExecutionError) as exc_info:
            await client.generate_structured_analysis("Sys", "User")

        assert "Gemini API execution error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_structured_analysis_empty_response(mock_settings: Settings) -> None:
    """Verify empty response text raises AgentExecutionError."""
    mock_response = MagicMock()
    mock_response.text = ""
    mock_response.parsed = None

    with patch("google.genai.Client") as mock_genai_cls:
        mock_client_inst = MagicMock()
        mock_aio_models = MagicMock()
        mock_aio_models.generate_content = AsyncMock(return_value=mock_response)
        mock_client_inst.aio.models = mock_aio_models
        mock_genai_cls.return_value = mock_client_inst

        client = GeminiStructuredClient(settings=mock_settings)
        with pytest.raises(AgentExecutionError) as exc_info:
            await client.generate_structured_analysis("Sys", "User")

        assert "empty or missing text response" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_structured_analysis_schema_validation_error(
    mock_settings: Settings,
) -> None:
    """Verify malformed JSON or schema mismatch raises AgentSchemaValidationError."""
    invalid_json = '{"findings": "not_a_list"}'

    mock_response = MagicMock()
    mock_response.text = invalid_json

    with patch("google.genai.Client") as mock_genai_cls:
        mock_client_inst = MagicMock()
        mock_aio_models = MagicMock()
        mock_aio_models.generate_content = AsyncMock(return_value=mock_response)
        mock_client_inst.aio.models = mock_aio_models
        mock_genai_cls.return_value = mock_client_inst

        client = GeminiStructuredClient(settings=mock_settings)
        with pytest.raises(AgentSchemaValidationError) as exc_info:
            await client.generate_structured_analysis("Sys", "User")

        assert "schema validation" in str(exc_info.value).lower()
