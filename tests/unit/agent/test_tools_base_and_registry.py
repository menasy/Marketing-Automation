"""Unit tests for tool abstractions (ToolResult, BaseTool) and ToolRegistry."""

import pytest

from src.agent.tools.base import BaseTool, ToolResult
from src.agent.tools.registry import ToolRegistry


class DummyTestTool(BaseTool):
    """Dummy concrete tool for testing BaseTool contract and ToolRegistry dispatching."""

    def __init__(
        self,
        tool_name: str = "dummy_tool",
        tool_desc: str = "Dummy evidence tool for unit testing.",
        should_fail: bool = False,
        raise_exception: bool = False,
    ) -> None:
        """Initialize dummy tool with configurable behavior."""
        self._name = tool_name
        self._desc = tool_desc
        self._should_fail = should_fail
        self._raise_exception = raise_exception

    @property
    def name(self) -> str:
        """Return tool name."""
        return self._name

    @property
    def description(self) -> str:
        """Return tool description."""
        return self._desc

    @property
    def parameters_schema(self) -> dict[str, object]:
        """Return JSON schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "Unique campaign ID to retrieve evidence for.",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of records to fetch.",
                },
            },
            "required": ["campaign_id"],
        }

    async def execute(self, **kwargs: object) -> ToolResult:
        """Execute dummy tool logic."""
        if self._raise_exception:
            raise RuntimeError("Internal tool failure simulation")

        if self._should_fail:
            return ToolResult(success=False, error="Failed to fetch evidence for target campaign")

        campaign_id = kwargs.get("campaign_id", "unknown")
        count = kwargs.get("count", 1)
        return ToolResult(
            success=True,
            data={"campaign_id": campaign_id, "count": count, "evidence": ["fact_1", "fact_2"]},
        )


def test_tool_result_to_llm_text_structured_data() -> None:
    """Verify ToolResult formats dict and list data as JSON strings."""
    result_dict = ToolResult(success=True, data={"status": "active", "spend": 150.5})
    assert result_dict.to_llm_text() == '{"status": "active", "spend": 150.5}'

    result_list = ToolResult(success=True, data=["record_1", "record_2"])
    assert result_list.to_llm_text() == '["record_1", "record_2"]'


def test_tool_result_to_llm_text_primitive_and_none() -> None:
    """Verify ToolResult formats primitive data and None correctly."""
    result_str = ToolResult(success=True, data="Simple fact statement")
    assert result_str.to_llm_text() == "Simple fact statement"

    result_int = ToolResult(success=True, data=42)
    assert result_int.to_llm_text() == "42"

    result_none = ToolResult(success=True, data=None)
    assert result_none.to_llm_text() == "Success"


def test_tool_result_to_llm_text_failure() -> None:
    """Verify ToolResult formats failure error messages."""
    result_error = ToolResult(success=False, error="Database connection timeout")
    assert result_error.to_llm_text() == "Database connection timeout"

    result_no_error = ToolResult(success=False, error=None)
    assert result_no_error.to_llm_text() == "Unknown error"


def test_registry_registration_and_duplicate_rejection() -> None:
    """Verify successful tool registration and ValueError rejection on duplicate name."""
    registry = ToolRegistry()
    tool1 = DummyTestTool(tool_name="get_campaign_evidence")

    registry.register(tool1)
    assert registry.get("get_campaign_evidence") is tool1
    assert registry.list_tools() == ["get_campaign_evidence"]

    tool_duplicate = DummyTestTool(tool_name="get_campaign_evidence")
    with pytest.raises(ValueError, match="Tool 'get_campaign_evidence' is already registered"):
        registry.register(tool_duplicate)


@pytest.mark.asyncio
async def test_registry_execute_success() -> None:
    """Verify ToolRegistry dispatches execution to registered tool with kwargs."""
    registry = ToolRegistry()
    tool = DummyTestTool(tool_name="fetch_evidence")
    registry.register(tool)

    result = await registry.execute("fetch_evidence", campaign_id="cmp-999", count=3)
    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["campaign_id"] == "cmp-999"
    assert result.data["count"] == 3
    assert result.error is None


@pytest.mark.asyncio
async def test_registry_execute_missing_tool() -> None:
    """Verify ToolRegistry handles missing tool execution gracefully."""
    registry = ToolRegistry()

    result = await registry.execute("non_existent_tool")
    assert result.success is False
    assert result.data is None
    assert result.error == "Tool 'non_existent_tool' not found"


@pytest.mark.asyncio
async def test_registry_execute_tool_exception_handling() -> None:
    """Verify ToolRegistry catches unhandled tool exceptions and returns ToolResult error."""
    registry = ToolRegistry()
    failing_tool = DummyTestTool(tool_name="failing_tool", raise_exception=True)
    registry.register(failing_tool)

    result = await registry.execute("failing_tool")
    assert result.success is False
    assert result.data is None
    assert result.error == "Internal tool failure simulation"


def test_registry_get_function_declarations() -> None:
    """Verify get_function_declarations exports schema format compatible with Gemini API."""
    registry = ToolRegistry()
    tool1 = DummyTestTool(tool_name="tool_a", tool_desc="First test tool")
    tool2 = DummyTestTool(tool_name="tool_b", tool_desc="Second test tool")

    registry.register(tool1)
    registry.register(tool2)

    declarations = registry.get_function_declarations()
    assert len(declarations) == 2

    assert declarations[0]["name"] == "tool_a"
    assert declarations[0]["description"] == "First test tool"
    assert "parameters" in declarations[0]
    assert isinstance(declarations[0]["parameters"], dict)

    assert declarations[1]["name"] == "tool_b"
    assert declarations[1]["description"] == "Second test tool"
