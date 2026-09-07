"""Base contracts and data models for read-only evidence retrieval tools."""

import json
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Standardized output model for tool execution.

    ToolResult is frozen to prevent mutable state leakage across agent reasoning loops.
    """

    success: bool
    data: dict[str, object] | Sequence[object] | str | int | float | bool | None = None
    error: str | None = None

    def to_llm_text(self) -> str:
        """Format tool result as a deterministic string representation for LLM grounding."""

        if not self.success:
            return self.error if self.error else "Unknown error"

        if isinstance(self.data, (dict, list, tuple)):
            return json.dumps(self.data, ensure_ascii=False)

        if self.data is None:
            return "Success"
        return str(self.data)


class BaseTool(ABC):
    """Abstract base class for all read-only evidence retrieval agent tools.

    Subclasses must declare tool metadata (`name`, `description`, `parameters_schema`)
    and implement the async `execute` method.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the tool used by LLM function dispatching."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Detailed description of tool capability and parameters for LLM grounding."""

    @property
    @abstractmethod
    def parameters_schema(self) -> dict[str, object]:
        """JSON Schema describing parameter names, types, descriptions, and required fields."""

    @abstractmethod
    async def execute(self, **kwargs: object) -> ToolResult:
        """Execute the tool with given arguments and return a frozen ToolResult."""
