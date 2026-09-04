from enum import StrEnum


class Severity(StrEnum):
    """Severity classification levels for detected statistical anomalies."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
