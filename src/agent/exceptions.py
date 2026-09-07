"""Domain and runtime exception definitions for AI Agent operations."""


class AgentBaseError(Exception):
    """Base exception class for all AI Agent errors."""


class AgentExecutionError(AgentBaseError):
    """Exception raised when Gemini API execution fails (network, 429 rate limit, 500 error)."""


class AgentSchemaValidationError(AgentBaseError):
    """Exception raised when LLM response fails JSON parsing or Pydantic schema validation."""
