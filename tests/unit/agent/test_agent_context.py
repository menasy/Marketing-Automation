"""Unit tests for AgentContext runtime session context."""

from src.agent.runtime.context import AgentContext
from src.domain.models.evidence_dossier import EvidenceDossier


def test_agent_context_initialization() -> None:
    """Verify AgentContext initializes correctly with slot fields and default timestamp."""
    dossier = EvidenceDossier(
        target_date="2026-09-03",
        baseline_window="2026-08-05 to 2026-09-02",
        total_anomalies_detected=5,
        total_campaigns_impacted=2,
        top_campaign_evidence=(),
    )

    ctx = AgentContext(
        execution_id="exec-uuid-1234",
        target_date="2026-09-03",
        dossier=dossier,
    )

    assert ctx.execution_id == "exec-uuid-1234"
    assert ctx.target_date == "2026-09-03"
    assert ctx.dossier == dossier
    assert ctx.metadata == {}
    assert "T" in ctx.created_at  # ISO 8601 format check


def test_agent_context_custom_metadata() -> None:
    """Verify AgentContext accepts custom metadata dictionary."""
    dossier = EvidenceDossier(
        target_date="2026-09-03",
        baseline_window="2026-08-05 to 2026-09-02",
        total_anomalies_detected=0,
        total_campaigns_impacted=0,
        top_campaign_evidence=(),
    )

    ctx = AgentContext(
        execution_id="exec-uuid-5678",
        target_date="2026-09-03",
        dossier=dossier,
        metadata={"environment": "testing", "channel": "slack"},
    )

    assert ctx.metadata["environment"] == "testing"
    assert ctx.metadata["channel"] == "slack"
