"""Asynchronous Gemini LLM client enforcing temperature=0.0 and BatchAnalysisResult schema."""

import logging
from abc import ABC, abstractmethod

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from src.agent.exceptions import AgentExecutionError, AgentSchemaValidationError
from src.agent.schemas.reasoning import BatchAnalysisResult
from src.infrastructure.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class IStructuredLLMClient(ABC):
    """Abstract interface for structured LLM reasoning clients."""

    @abstractmethod
    async def generate_structured_analysis(
        self, system_instruction: str, user_prompt: str
    ) -> BatchAnalysisResult:
        """Generate structured BatchAnalysisResult analysis from system instruction and prompt."""


class GeminiStructuredClient(IStructuredLLMClient):
    """Asynchronous Gemini LLM client enforcing strict JSON output against BatchAnalysisResult."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize Gemini client with API key and model configuration."""
        app_settings = settings or get_settings()
        self._api_key = api_key or app_settings.gemini_api_key
        self._model_name = model_name or app_settings.gemini_model

        if not self._api_key:
            logger.warning(
                "Gemini API key is empty. API calls will fail unless configured via environment."
            )

        self._client = genai.Client(api_key=self._api_key)

    async def generate_structured_analysis(
        self, system_instruction: str, user_prompt: str
    ) -> BatchAnalysisResult:
        """Executes Gemini API call enforcing temperature=0.0 and response_schema."""
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=BatchAnalysisResult,
        )

        try:
            logger.info("Invoking Gemini structured API [model=%s]", self._model_name)
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=user_prompt,
                config=config,
            )
        except genai_errors.APIError as exc:
            logger.error("Gemini API error: %s", str(exc))
            raise AgentExecutionError(f"Gemini API execution error: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error calling Gemini API: %s", str(exc))
            raise AgentExecutionError(f"Gemini client communication error: {exc}") from exc

        if not response or not response.text:
            if hasattr(response, "parsed") and isinstance(response.parsed, BatchAnalysisResult):
                return response.parsed
            raise AgentExecutionError("Gemini API returned an empty or missing text response.")

        raw_text = response.text.strip()

        try:
            return BatchAnalysisResult.model_validate_json(raw_text)
        except ValidationError as exc:
            logger.error("Schema validation failed for Gemini response: %s", str(exc))
            raise AgentSchemaValidationError(
                f"Gemini response failed BatchAnalysisResult schema validation: {exc}"
            ) from exc
        except Exception as exc:
            logger.error("JSON decode failed for Gemini response: %s", str(exc))
            raise AgentSchemaValidationError(
                f"Failed to decode JSON from Gemini response: {exc}"
            ) from exc
