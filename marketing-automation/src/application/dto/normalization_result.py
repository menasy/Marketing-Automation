from dataclasses import dataclass

from src.domain.models.ad_record import NormalizedAdRecord


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """DTO containing the output of unified data normalization and execution audit metrics."""

    records: list[NormalizedAdRecord]
    total_raw_records_read: int
    skipped_records_count: int
    summary_by_platform: dict[str, int]
