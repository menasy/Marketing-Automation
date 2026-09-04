from typing import Protocol

from src.domain.models.briefing import ExecutiveBriefing


class INotificationService(Protocol):
    """Abstract port for dispatching executive briefings via notification channels."""

    def send(self, briefing: ExecutiveBriefing) -> bool:
        """Dispatches an executive briefing to notification destinations."""
        ...
