from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class BriefingRequest(BaseModel):
    """Data Transfer Object for briefing generation request parameters."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    date_from: str | None = Field(default=None, description="Optional start date ISO string")
    date_to: str | None = Field(default=None, description="Optional end date ISO string")
    force_refresh: bool = Field(default=False, description="Whether to bypass cached briefing")
    strict_validation: bool = Field(
        default=False, description="Whether to raise error on LLM output discrepancy"
    )


class BriefingResponse(BaseModel):
    """Data Transfer Object for briefing generation response payload."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    summary: str = Field(..., description="High-level executive summary")
    raw_markdown: str = Field(..., description="Full raw markdown briefing text")
    critical_findings: list[str] = Field(
        default_factory=list, description="List of critical anomaly finding bullet points"
    )
    recommended_actions: list[str] = Field(
        default_factory=list, description="List of recommended action bullet points"
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when briefing was generated",
    )
    is_fallback: bool = Field(
        default=False, description="Whether briefing was generated via deterministic fallback"
    )
    validation_warnings: list[str] = Field(
        default_factory=list, description="Validation discrepancy warnings if any"
    )
