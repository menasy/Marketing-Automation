from typing import Protocol

from src.domain.models.ad_record import NormalizedAdRecord
from src.domain.models.anomaly import AnomalyItem


class IAnomalyDetector(Protocol):
    """Abstract port for detecting statistical anomalies in normalized marketing data."""

    def detect(self, records: list[NormalizedAdRecord], window_days: int) -> list[AnomalyItem]:
        """Detects anomalies across normalized records using historical baseline window."""
        ...
