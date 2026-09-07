"""Registry for tool lifecycle management, dispatching, and Gemini function schema export."""

import logging

from src.agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for managing read-only evidence retrieval tools.

    Provides tool registration, lookup, execution dispatching with safe error boundaries,
    and export of Gemini API-compatible function declarations.
    """

    def __init__(self) -> None:
        """Initialize an empty tool registry."""
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance into the registry.

        Args:
            tool: BaseTool instance to register.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def get(self, name: str) -> BaseTool | None:
        """Retrieve a registered tool by name.

        Args:
            name: Unique name of the tool.

        Returns:
            Registered BaseTool instance if found, or None.
        """
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """Return list of registered tool names."""
        return list(self._tools.keys())

    def get_function_declarations(self) -> list[dict[str, object]]:
        """Export registered tools as JSON Schema function declarations compatible with Gemini API.

        Returns:
            List of dictionaries matching Gemini function declaration parameters.
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters_schema,
            }
            for tool in self._tools.values()
        ]

    async def execute(self, name: str, **kwargs: object) -> ToolResult:
        """Safely execute a tool by name with provided keyword arguments.

        Catches tool execution exceptions and missing tool errors to return a frozen,
        deterministic ToolResult object without raising runtime exceptions.

        Args:
            name: Unique tool identifier.
            **kwargs: Dynamic arguments forwarded to the tool's execute method.

        Returns:
            ToolResult representing success or failure.
        """
        tool = self.get(name)
        if tool is None:
            logger.warning("Attempted execution of unregistered tool: %s", name)
            return ToolResult(success=False, error=f"Tool '{name}' not found")

        try:
            result = await tool.execute(**kwargs)
            logger.info("Executed tool '%s' (success=%s)", name, result.success)
            return result
        except Exception as exc:
            logger.error("Error executing tool '%s': %s", name, str(exc), exc_info=True)
            return ToolResult(success=False, error=str(exc))
