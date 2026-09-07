from dataclasses import dataclass

from src.domain.enums.platform import Platform


@dataclass(frozen=True, slots=True)
class NormalizedAdRecord:
    """Immutable domain representation of a normalized advertising performance record."""

    date: str
    platform: Platform
    campaign_name: str
    country: str
    currency: str
    spend: float
    impressions: int
    clicks: int
    conversions: float
    conversion_value: float
    ctr: float | None = None
    cpc: float | None = None
    cpm: float | None = None
    cpa: float | None = None
    roas: float | None = None
