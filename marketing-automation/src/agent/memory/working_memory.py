"""In-memory stateless execution state tracker for recording runtime telemetry and audit events."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MemoryEvent:
    """Immutable record of an execution state event within working memory."""

    timestamp: str
    event_type: str
    description: str
    details: dict[str, object]


class WorkingMemory:
    """In-memory, transient execution state tracker for pipeline observability and auditability."""

    def __init__(self) -> None:
        """Initialize empty working memory event log."""
        self._events: list[MemoryEvent] = []

    def record_step(self, step_name: str, description: str, **metadata: object) -> None:
        """Records a step transition event into working memory.

        Args:
            step_name: Identifier for the execution pipeline step.
            description: Human-readable description of the step transition.
            **metadata: Additional keyword metadata associated with the step.
        """
        try:
            details: dict[str, object] = {"step_name": step_name, **metadata}
            event = MemoryEvent(
                timestamp=datetime.now(UTC).isoformat(),
                event_type="STEP",
                description=description,
                details=details,
            )
            self._events.append(event)
        except Exception as exc:
            logger.warning("Failed to record step event in WorkingMemory: %s", exc)

    def record_tool_call(
        self,
        tool_name: str,
        parameters: dict[str, object],
        success: bool,
        error: str | None = None,
    ) -> None:
        """Records tool execution metadata and results.

        Args:
            tool_name: Name of executed tool.
            parameters: Input parameters provided to tool.
            success: Execution status flag.
            error: Optional error string if tool execution failed.
        """
        try:
            details: dict[str, object] = {
                "tool_name": tool_name,
                "parameters": parameters,
                "success": success,
                "error": error,
            }
            event = MemoryEvent(
                timestamp=datetime.now(UTC).isoformat(),
                event_type="TOOL_CALL",
                description=f"Executed tool {tool_name} (success={success})",
                details=details,
            )
            self._events.append(event)
        except Exception as exc:
            logger.warning("Failed to record tool call event in WorkingMemory: %s", exc)

    def record_hypothesis(
        self, campaign_name: str, statement: str, selected: bool, confidence: float
    ) -> None:
        """Records evaluated hypothesis details.

        Args:
            campaign_name: Associated campaign identifier/name.
            statement: Evaluated hypothesis statement.
            selected: True if hypothesis was selected as primary diagnosis.
            confidence: Evaluated confidence score (0.0 to 1.0).
        """
        try:
            details: dict[str, object] = {
                "campaign_name": campaign_name,
                "statement": statement,
                "selected": selected,
                "confidence": confidence,
            }
            event = MemoryEvent(
                timestamp=datetime.now(UTC).isoformat(),
                event_type="HYPOTHESIS_EVALUATION",
                description=(
                    f"Evaluated hypothesis for campaign '{campaign_name}' (selected={selected})"
                ),
                details=details,
            )
            self._events.append(event)
        except Exception as exc:
            logger.warning("Failed to record hypothesis event in WorkingMemory: %s", exc)

    def record_verification(
        self,
        is_valid: bool,
        errors: tuple[str, ...],
        warnings: tuple[str, ...],
    ) -> None:
        """Records deterministic verification gate results.

        Args:
            is_valid: Flag indicating whether verification passed.
            errors: Tuple of validation error messages.
            warnings: Tuple of validation warning messages.
        """
        try:
            details: dict[str, object] = {
                "is_valid": is_valid,
                "errors": list(errors),
                "warnings": list(warnings),
            }
            event = MemoryEvent(
                timestamp=datetime.now(UTC).isoformat(),
                event_type="VERIFICATION",
                description=f"Verification gate audited (is_valid={is_valid})",
                details=details,
            )
            self._events.append(event)
        except Exception as exc:
            logger.warning("Failed to record verification event in WorkingMemory: %s", exc)

    def get_events(self) -> tuple[MemoryEvent, ...]:
        """Returns an immutable snapshot tuple of all recorded events."""
        return tuple(self._events)

    def to_dict(self) -> dict[str, object]:
        """Exports serialized execution telemetry suitable for logging or reporting metadata."""
        return {
            "total_events": len(self._events),
            "events": [
                {
                    "timestamp": event.timestamp,
                    "event_type": event.event_type,
                    "description": event.description,
                    "details": event.details,
                }
                for event in self._events
            ],
        }

    def clear(self) -> None:
        """Flushes all recorded memory events."""
        self._events.clear()
