from enum import StrEnum


class MetricType(StrEnum):
    """Marketing metrics evaluated by normalization and anomaly detection engines."""

    SPEND = "spend"
    IMPRESSIONS = "impressions"
    CLICKS = "clicks"
    CONVERSIONS = "conversions"
    CONVERSION_VALUE = "conversion_value"
    CTR = "ctr"
    CPC = "cpc"
    CPM = "cpm"
    CPA = "cpa"
    ROAS = "roas"


class MetricDirection(StrEnum):
    """Desired performance movement for a given metric."""

    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    NEUTRAL = "neutral"
