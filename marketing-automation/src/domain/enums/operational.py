"""Operational findings enums for root-cause issues and actionable recommendations."""

from enum import StrEnum


class IssueType(StrEnum):
    """Classification of root-cause anomaly issues."""

    PERFORMANCE = "performance"
    DATA_QUALITY = "data_quality"
    MIXED = "mixed"


class ActionCategory(StrEnum):
    """Operational action categories."""

    BUDGET = "budget"
    BID = "bid"
    CREATIVE = "creative"
    TRACKING = "tracking"


class BudgetAction(StrEnum):
    """Concrete actions for budget management."""

    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    HOLD = "HOLD"
    REALLOCATE = "REALLOCATE"


class BidAction(StrEnum):
    """Concrete actions for bidding strategy."""

    ADJUST_TARGET_CPA_ROAS = "ADJUST_TARGET_CPA_ROAS"
    SWITCH_STRATEGY = "SWITCH_STRATEGY"
    NO_CHANGE = "NO_CHANGE"


class CreativeAction(StrEnum):
    """Concrete actions for creative and landing page optimizations."""

    REFRESH_FATIGUED_CREATIVES = "REFRESH_FATIGUED_CREATIVES"
    RUN_A_B_TEST = "RUN_A_B_TEST"
    AUDIT_LANDING_PAGE = "AUDIT_LANDING_PAGE"
    NO_ACTION = "NO_ACTION"


class TrackingAction(StrEnum):
    """Concrete actions for tracking and attribution diagnostics."""

    AUDIT_PIXEL_CAPI = "AUDIT_PIXEL_CAPI"
    VERIFY_GTM_TAGS = "VERIFY_GTM_TAGS"
    NO_ACTION = "NO_ACTION"
