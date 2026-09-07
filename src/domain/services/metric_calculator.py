import math
from dataclasses import replace

from src.domain.models.ad_record import NormalizedAdRecord


class MetricCalculator:
    """Pure domain service for calculating derived advertising performance metrics.

    Enforces defensive zero-division math and strict floating-point precision rules.
    """

    @staticmethod
    def _is_invalid_number(val: float | int) -> bool:
        """Check if a numeric value is NaN, infinite, or None."""
        if val is None:
            return True
        return math.isnan(val) or math.isinf(val)

    @classmethod
    def calculate_ctr(cls, clicks: int, impressions: int) -> float | None:
        """Calculate Click-Through Rate (CTR): clicks / impressions.

        Returns None if impressions <= 0 or clicks < 0.
        """
        if cls._is_invalid_number(clicks) or cls._is_invalid_number(impressions):
            return None
        if impressions <= 0 or clicks < 0:
            return None
        return round(clicks / impressions, 4)

    @classmethod
    def calculate_cpc(cls, spend: float, clicks: int) -> float | None:
        """Calculate Cost Per Click (CPC): spend / clicks.

        Returns None if clicks <= 0 or spend < 0.
        """
        if cls._is_invalid_number(spend) or cls._is_invalid_number(clicks):
            return None
        if clicks <= 0 or spend < 0:
            return None
        return round(spend / clicks, 2)

    @classmethod
    def calculate_cpm(cls, spend: float, impressions: int) -> float | None:
        """Calculate Cost Per Mille (CPM): (spend / impressions) * 1000.

        Returns None if impressions <= 0 or spend < 0.
        """
        if cls._is_invalid_number(spend) or cls._is_invalid_number(impressions):
            return None
        if impressions <= 0 or spend < 0:
            return None
        return round((spend / impressions) * 1000.0, 2)

    @classmethod
    def calculate_cpa(cls, spend: float, conversions: float) -> float | None:
        """Calculate Cost Per Acquisition (CPA): spend / conversions.

        Returns None if conversions <= 0 or spend < 0.
        """
        if cls._is_invalid_number(spend) or cls._is_invalid_number(conversions):
            return None
        if conversions <= 0 or spend < 0:
            return None
        return round(spend / conversions, 2)

    @classmethod
    def calculate_roas(cls, conversion_value: float, spend: float) -> float | None:
        """Calculate Return On Ad Spend (ROAS): conversion_value / spend.

        Returns None if spend <= 0 or conversion_value < 0.
        """
        if cls._is_invalid_number(conversion_value) or cls._is_invalid_number(spend):
            return None
        if spend <= 0 or conversion_value < 0:
            return None
        return round(conversion_value / spend, 2)

    @classmethod
    def enrich_record(cls, record: NormalizedAdRecord) -> NormalizedAdRecord:
        """Return a new immutable NormalizedAdRecord enriched with computed metrics."""
        ctr = cls.calculate_ctr(record.clicks, record.impressions)
        cpc = cls.calculate_cpc(record.spend, record.clicks)
        cpm = cls.calculate_cpm(record.spend, record.impressions)
        cpa = cls.calculate_cpa(record.spend, record.conversions)
        roas = cls.calculate_roas(record.conversion_value, record.spend)

        return replace(
            record,
            ctr=ctr,
            cpc=cpc,
            cpm=cpm,
            cpa=cpa,
            roas=roas,
        )
