"""Agent runtime session execution context."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.agent.memory.working_memory import WorkingMemory
from src.agent.schemas.reasoning import BatchAnalysisResult
from src.domain.models.evidence_dossier import EvidenceDossier


@dataclass(slots=True)
class AgentContext:
    """Session execution context holding target date, EvidenceDossier, and run metadata."""

    execution_id: str
    target_date: str
    dossier: EvidenceDossier
    result: BatchAnalysisResult | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    working_memory: WorkingMemory = field(default_factory=WorkingMemory)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
