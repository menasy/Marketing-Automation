from typing import Protocol

from src.domain.models.anomaly import AnomalyItem
from src.domain.models.briefing import ExecutiveBriefing


class ILLMService(Protocol):
    """Abstract port for generating evidence-grounded executive briefings via LLM."""

    def generate_briefing(self, anomalies: list[AnomalyItem]) -> ExecutiveBriefing:
        """Generates an executive briefing grounded strictly on provided detected anomalies."""
        ...
