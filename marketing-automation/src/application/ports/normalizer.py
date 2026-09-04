from typing import Protocol

from src.domain.models.ad_record import NormalizedAdRecord


class INormalizer(Protocol):
    """Abstract port for normalizing raw platform records to unified domain records."""

    def normalize(self, raw_records: list[dict[str, object]]) -> list[NormalizedAdRecord]:
        """Normalizes raw dictionary records into canonical NormalizedAdRecord instances."""
        ...
