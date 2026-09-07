"""Agent package for Gemini autonomous reasoning and structured diagnosis."""

from src.agent.exceptions import (
    AgentBaseError,
    AgentExecutionError,
    AgentSchemaValidationError,
)
from src.agent.guardrails.fallback import DeterministicFallbackGenerator
from src.agent.guardrails.verifier import (
    GroundingVerifier,
    NumericVerifier,
    OutputVerifier,
    VerificationResult,
)
from src.agent.memory import MemoryEvent, WorkingMemory
from src.agent.runtime.context import AgentContext
from src.agent.runtime.gemini_client import (
    GeminiStructuredClient,
    IStructuredLLMClient,
)
from src.agent.runtime.orchestrator import BatchReasoningOrchestrator
from src.agent.tools.base import BaseTool, ToolResult
from src.agent.tools.evidence_tools import (
    GetCampaignMetricsTool,
    GetHistoricalPerformanceTool,
    InspectDataQualityTool,
)
from src.agent.tools.registry import ToolRegistry

__all__ = [
    "AgentBaseError",
    "AgentExecutionError",
    "AgentSchemaValidationError",
    "AgentContext",
    "MemoryEvent",
    "WorkingMemory",
    "IStructuredLLMClient",
    "GeminiStructuredClient",
    "BatchReasoningOrchestrator",
    "BaseTool",
    "ToolResult",
    "ToolRegistry",
    "GetCampaignMetricsTool",
    "GetHistoricalPerformanceTool",
    "InspectDataQualityTool",
    "VerificationResult",
    "NumericVerifier",
    "GroundingVerifier",
    "OutputVerifier",
    "DeterministicFallbackGenerator",
]
