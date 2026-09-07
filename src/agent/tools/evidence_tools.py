"""Concrete read-only evidence retrieval tools for agent reasoning grounding."""

import logging
from collections.abc import Sequence

from src.agent.tools.base import BaseTool, ToolResult
from src.domain.models.ad_record import NormalizedAdRecord
from src.domain.models.evidence_dossier import CampaignEvidence, EvidenceDossier

logger = logging.getLogger(__name__)


class GetCampaignMetricsTool(BaseTool):
    """Tool for retrieving current target-date metrics and baseline values for a campaign."""

    def __init__(self, dossier_or_campaigns: EvidenceDossier | Sequence[CampaignEvidence]) -> None:
        """Initialize tool with EvidenceDossier or sequence of CampaignEvidence instances."""
        if isinstance(dossier_or_campaigns, EvidenceDossier):
            self._campaigns: tuple[CampaignEvidence, ...] = (
                dossier_or_campaigns.top_campaign_evidence
            )
        else:
            self._campaigns = tuple(dossier_or_campaigns)

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        return "get_campaign_metrics"

    @property
    def description(self) -> str:
        """Tool description for LLM function calling."""
        return (
            "Returns current target-date metrics and baseline values for a specific campaign name."
        )

    @property
    def parameters_schema(self) -> dict[str, object]:
        """JSON Schema for parameter validation."""
        return {
            "type": "object",
            "properties": {
                "campaign_name": {
                    "type": "string",
                    "description": "Exact name of the campaign.",
                }
            },
            "required": ["campaign_name"],
        }

    async def execute(self, **kwargs: object) -> ToolResult:
        """Execute campaign metric extraction."""
        try:
            campaign_name = kwargs.get("campaign_name")
            if not isinstance(campaign_name, str) or not campaign_name.strip():
                return ToolResult(success=False, error="Parameter 'campaign_name' is required.")

            target_campaign = next(
                (c for c in self._campaigns if c.campaign_name == campaign_name), None
            )

            if target_campaign is None:
                return ToolResult(
                    success=False,
                    error=f"Campaign '{campaign_name}' not found in evidence dossier.",
                )

            metrics_data: dict[str, dict[str, object]] = {}
            for name, m in target_campaign.metrics.items():
                metrics_data[name] = {
                    "metric_name": m.metric_name,
                    "current_value": m.current_value,
                    "baseline_value": m.baseline_value,
                    "delta_pct": m.delta_pct,
                    "z_score": m.z_score,
                    "is_anomaly": m.is_anomaly,
                }

            result_payload: dict[str, object] = {
                "campaign_id": target_campaign.campaign_id,
                "campaign_name": target_campaign.campaign_name,
                "platform": target_campaign.platform,
                "account_id": target_campaign.account_id,
                "country": target_campaign.country,
                "spend": target_campaign.spend,
                "financial_impact_score": target_campaign.financial_impact_score,
                "metrics": metrics_data,
            }

            return ToolResult(success=True, data=result_payload)
        except Exception as exc:
            logger.error("Error executing GetCampaignMetricsTool: %s", str(exc), exc_info=True)
            return ToolResult(success=False, error=str(exc))


class GetHistoricalPerformanceTool(BaseTool):
    """Tool for retrieving daily historical time-series performance metrics prior to target date."""

    def __init__(self, records: Sequence[NormalizedAdRecord], target_date: str) -> None:
        """Initialize tool with historical ad records and target evaluation date."""
        self._records = tuple(records)
        self._target_date = target_date

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        return "get_historical_performance"

    @property
    def description(self) -> str:
        """Tool description for LLM function calling."""
        return (
            "Returns daily historical time-series performance metrics for a specific campaign "
            "over the preceding N days strictly prior to the target evaluation date."
        )

    @property
    def parameters_schema(self) -> dict[str, object]:
        """JSON Schema for parameter validation."""
        return {
            "type": "object",
            "properties": {
                "campaign_name": {
                    "type": "string",
                    "description": "Name of the campaign.",
                },
                "days": {
                    "type": "integer",
                    "description": (
                        "Number of historical days to retrieve (between 7 and 30). Default is 14."
                    ),
                    "default": 14,
                },
            },
            "required": ["campaign_name"],
        }

    async def execute(self, **kwargs: object) -> ToolResult:
        """Execute historical performance extraction with look-ahead bias defense."""
        try:
            campaign_name = kwargs.get("campaign_name")
            if not isinstance(campaign_name, str) or not campaign_name.strip():
                return ToolResult(success=False, error="Parameter 'campaign_name' is required.")

            days_raw = kwargs.get("days", 14)
            try:
                days = int(days_raw) if isinstance(days_raw, (int, str, float)) else 14
            except (ValueError, TypeError):
                days = 14

            clamped_days = max(7, min(30, days))

            # STRICT LOOK-AHEAD BIAS DEFENSE: date < target_date (t < target_date)
            matching_records = [
                r
                for r in self._records
                if r.campaign_name == campaign_name and r.date < self._target_date
            ]

            if not matching_records:
                return ToolResult(
                    success=False,
                    error=(
                        f"No historical records found for campaign '{campaign_name}' "
                        f"prior to '{self._target_date}'."
                    ),
                )

            # Sort descending by date to take the N most recent historical days
            sorted_desc = sorted(matching_records, key=lambda r: r.date, reverse=True)
            selected_slice = sorted_desc[:clamped_days]
            # Sort ascending by date for clean chronological presentation
            sorted_asc = sorted(selected_slice, key=lambda r: r.date)

            time_series: list[dict[str, object]] = [
                {
                    "date": r.date,
                    "spend": r.spend,
                    "impressions": r.impressions,
                    "clicks": r.clicks,
                    "ctr": r.ctr,
                    "cpc": r.cpc,
                    "conversions": r.conversions,
                    "cpa": r.cpa,
                    "roas": r.roas,
                }
                for r in sorted_asc
            ]

            return ToolResult(success=True, data=time_series)
        except Exception as exc:
            logger.error(
                "Error executing GetHistoricalPerformanceTool: %s", str(exc), exc_info=True
            )
            return ToolResult(success=False, error=str(exc))


class InspectDataQualityTool(BaseTool):
    """Tool for inspecting objective data quality and anomaly signals for a campaign."""

    def __init__(self, dossier_or_campaigns: EvidenceDossier | Sequence[CampaignEvidence]) -> None:
        """Initialize tool with EvidenceDossier or sequence of CampaignEvidence instances."""
        if isinstance(dossier_or_campaigns, EvidenceDossier):
            self._campaigns: tuple[CampaignEvidence, ...] = (
                dossier_or_campaigns.top_campaign_evidence
            )
        else:
            self._campaigns = tuple(dossier_or_campaigns)

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        return "inspect_data_quality"

    @property
    def description(self) -> str:
        """Tool description for LLM function calling."""
        return (
            "Returns objective data quality and anomaly signals for a given campaign "
            "without subjective diagnoses."
        )

    @property
    def parameters_schema(self) -> dict[str, object]:
        """JSON Schema for parameter validation."""
        return {
            "type": "object",
            "properties": {
                "campaign_name": {
                    "type": "string",
                    "description": "Name of the campaign.",
                }
            },
            "required": ["campaign_name"],
        }

    async def execute(self, **kwargs: object) -> ToolResult:
        """Execute data quality signal inspection."""
        try:
            campaign_name = kwargs.get("campaign_name")
            if not isinstance(campaign_name, str) or not campaign_name.strip():
                return ToolResult(success=False, error="Parameter 'campaign_name' is required.")

            target_campaign = next(
                (c for c in self._campaigns if c.campaign_name == campaign_name), None
            )

            if target_campaign is None:
                return ToolResult(
                    success=False,
                    error=f"Campaign '{campaign_name}' not found in evidence dossier.",
                )

            signals_data: list[dict[str, object]] = [
                {
                    "signal_type": sig.signal_type.value,
                    "is_triggered": sig.is_triggered,
                    "metric_name": sig.metric_name,
                    "current_value": sig.current_value,
                    "baseline_value": sig.baseline_value,
                    "delta_pct": sig.delta_pct,
                    "factual_statement": sig.factual_statement,
                }
                for sig in target_campaign.data_quality_signals
            ]

            result_payload: dict[str, object] = {
                "campaign_name": target_campaign.campaign_name,
                "signals": signals_data,
            }

            return ToolResult(success=True, data=result_payload)
        except Exception as exc:
            logger.error("Error executing InspectDataQualityTool: %s", str(exc), exc_info=True)
            return ToolResult(success=False, error=str(exc))
