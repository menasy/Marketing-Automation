from datetime import date

from pydantic import BaseModel, Field


class PipelineRequest(BaseModel):
    """Data Transfer Object representing parameters for pipeline execution."""

    google_csv_path: str | None = Field(
        default=None,
        description="Optional file path to Google Ads daily CSV export",
    )
    meta_csv_path: str | None = Field(
        default=None,
        description="Optional file path to Meta Ads daily CSV export",
    )
    window_days: int = Field(
        default=14,
        ge=1,
        le=90,
        description="Baseline historical window size in days for anomaly calculation",
    )
    reporting_currency: str = Field(
        default="USD",
        description="Target ISO currency code for financial normalization",
    )
    target_date: date | None = Field(
        default=None,
        description="Target evaluation date for baseline splitting and anomaly detection",
    )

    # Legacy / Backwards Compatibility Fields
    date_from: str | None = Field(
        default=None,
        description="Optional start date filter (ISO 8601 YYYY-MM-DD)",
    )
    date_to: str | None = Field(
        default=None,
        description="Optional end date filter (ISO 8601 YYYY-MM-DD)",
    )
    anomaly_window_days: int = Field(
        default=14,
        ge=1,
        le=90,
        description="Baseline historical window size in days for anomaly calculation",
    )
    zscore_threshold: float = Field(
        default=2.0,
        gt=0.0,
        description="Minimum absolute Z-score threshold to qualify as an anomaly",
    )
    force_refresh: bool = Field(
        default=False,
        description="Force re-normalization and re-calculation ignoring cached outputs",
    )
