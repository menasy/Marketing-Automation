from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class ExecutiveBriefing:
    """Immutable domain representation of an LLM-generated executive performance briefing."""

    summary: str
    raw_markdown: str
    critical_findings: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
