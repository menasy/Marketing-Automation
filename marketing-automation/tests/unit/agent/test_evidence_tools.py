"""Unit tests for concrete evidence retrieval tools and look-ahead bias defense."""

import pytest

from src.agent.tools.evidence_tools import (
    GetCampaignMetricsTool,
    GetHistoricalPerformanceTool,
    InspectDataQualityTool,
)
from src.agent.tools.registry import ToolRegistry
from src.domain.enums.platform import Platform
from src.domain.models.ad_record import NormalizedAdRecord
from src.domain.models.data_quality_signal import DataQualitySignal, DataQualitySignalType
from src.domain.models.evidence_dossier import CampaignEvidence, EvidenceDossier, MetricEvidence


@pytest.fixture
def sample_dossier() -> EvidenceDossier:
    """Fixture providing a mock EvidenceDossier with sample campaign metrics and signals."""
    metrics = {
        "spend": MetricEvidence(
            metric_name="spend",
            current_value=500.0,
            baseline_value=400.0,
            delta_pct=25.0,
            z_score=1.5,
            is_anomaly=False,
        ),
        "conversions": MetricEvidence(
            metric_name="conversions",
            current_value=0.0,
            baseline_value=50.0,
            delta_pct=-100.0,
            z_score=-3.5,
            is_anomaly=True,
        ),
    }

    signal = DataQualitySignal(
        signal_type=DataQualitySignalType.ZERO_CONVERSIONS_WITH_ACTIVE_SPEND,
        is_triggered=True,
        metric_name="conversions",
        current_value=0.0,
        baseline_value=50.0,
        delta_pct=-100.0,
        factual_statement="Spend is 500.00 but conversions dropped to 0.",
    )

    campaign = CampaignEvidence(
        campaign_id="cmp-101",
        campaign_name="US_Search_Brand",
        platform="google_ads",
        account_id="acc-01",
        country="US",
        spend=500.0,
        financial_impact_score=85.0,
        metrics=metrics,
        data_quality_signals=(signal,),
    )

    return EvidenceDossier(
        target_date="2026-09-03",
        baseline_window="2026-08-05 to 2026-09-02",
        total_anomalies_detected=1,
        total_campaigns_impacted=1,
        top_campaign_evidence=(campaign,),
    )


@pytest.fixture
def sample_ad_records() -> tuple[NormalizedAdRecord, ...]:
    """Fixture providing historical ad records spanning before, on, and after target date."""
    records = []
    # Historical records (t < 2026-09-03)
    for i in range(1, 20):
        day_str = f"{i:02d}"
        records.append(
            NormalizedAdRecord(
                date=f"2026-08-{day_str}",
                platform=Platform.GOOGLE_ADS,
                campaign_name="US_Search_Brand",
                country="US",
                currency="USD",
                spend=100.0 + i,
                impressions=1000 + (i * 10),
                clicks=100 + i,
                conversions=10.0 + (i * 0.5),
                conversion_value=200.0 + (i * 5.0),
                ctr=0.10,
                cpc=1.0,
                cpm=100.0,
                cpa=10.0,
                roas=2.0,
            )
        )

    # Target date and future records (t >= 2026-09-03) - MUST BE EXCLUDED BY LOOK-AHEAD DEFENSE
    records.append(
        NormalizedAdRecord(
            date="2026-09-03",
            platform=Platform.GOOGLE_ADS,
            campaign_name="US_Search_Brand",
            country="US",
            currency="USD",
            spend=500.0,
            impressions=2000,
            clicks=150,
            conversions=0.0,
            conversion_value=0.0,
        )
    )
    records.append(
        NormalizedAdRecord(
            date="2026-09-04",
            platform=Platform.GOOGLE_ADS,
            campaign_name="US_Search_Brand",
            country="US",
            currency="USD",
            spend=600.0,
            impressions=2200,
            clicks=160,
            conversions=0.0,
            conversion_value=0.0,
        )
    )

    return tuple(records)


@pytest.mark.asyncio
async def test_get_campaign_metrics_success(sample_dossier: EvidenceDossier) -> None:
    """Verify GetCampaignMetricsTool extracts campaign metrics successfully."""
    tool = GetCampaignMetricsTool(dossier_or_campaigns=sample_dossier)
    assert tool.name == "get_campaign_metrics"

    result = await tool.execute(campaign_name="US_Search_Brand")
    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["campaign_name"] == "US_Search_Brand"
    assert result.data["spend"] == 500.0

    metrics = result.data["metrics"]
    assert isinstance(metrics, dict)
    assert "spend" in metrics
    assert "conversions" in metrics
    assert metrics["conversions"]["is_anomaly"] is True


@pytest.mark.asyncio
async def test_get_campaign_metrics_unknown_and_missing(sample_dossier: EvidenceDossier) -> None:
    """Verify GetCampaignMetricsTool handles unknown campaign and missing parameters."""
    tool = GetCampaignMetricsTool(dossier_or_campaigns=sample_dossier)

    res_unknown = await tool.execute(campaign_name="Unknown_Campaign")
    assert res_unknown.success is False
    assert "not found" in str(res_unknown.error)

    res_missing = await tool.execute()
    assert res_missing.success is False
    assert "required" in str(res_missing.error)


@pytest.mark.asyncio
async def test_get_historical_performance_look_ahead_bias_defense(
    sample_ad_records: tuple[NormalizedAdRecord, ...],
) -> None:
    """Verify GetHistoricalPerformanceTool strictly excludes records with date >= target_date."""
    tool = GetHistoricalPerformanceTool(records=sample_ad_records, target_date="2026-09-03")
    assert tool.name == "get_historical_performance"

    result = await tool.execute(campaign_name="US_Search_Brand", days=14)
    assert result.success is True
    assert isinstance(result.data, list)

    dates = [row["date"] for row in result.data if isinstance(row, dict) and "date" in row]
    # Verify no records on or after target date exist in output
    assert "2026-09-03" not in dates
    assert "2026-09-04" not in dates
    assert all(d < "2026-09-03" for d in dates)


@pytest.mark.asyncio
async def test_get_historical_performance_days_clamping(
    sample_ad_records: tuple[NormalizedAdRecord, ...],
) -> None:
    """Verify days parameter is clamped between [7, 30]."""
    tool = GetHistoricalPerformanceTool(records=sample_ad_records, target_date="2026-09-03")

    # Lower bound clamping: days=2 should clamp to 7
    res_low = await tool.execute(campaign_name="US_Search_Brand", days=2)
    assert res_low.success is True
    assert isinstance(res_low.data, list)
    assert len(res_low.data) == 7

    # Upper bound clamping: days=50 should clamp to 30 (or all available historical records if < 30)
    res_high = await tool.execute(campaign_name="US_Search_Brand", days=50)
    assert res_high.success is True
    assert isinstance(res_high.data, list)
    assert len(res_high.data) == 19  # Total historical records available in fixture


@pytest.mark.asyncio
async def test_inspect_data_quality_success(sample_dossier: EvidenceDossier) -> None:
    """Verify InspectDataQualityTool returns objective data quality signals."""
    tool = InspectDataQualityTool(dossier_or_campaigns=sample_dossier)
    assert tool.name == "inspect_data_quality"

    result = await tool.execute(campaign_name="US_Search_Brand")
    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["campaign_name"] == "US_Search_Brand"

    signals = result.data["signals"]
    assert isinstance(signals, list)
    assert len(signals) == 1
    assert signals[0]["signal_type"] == "zero_conversions_with_active_spend"
    assert signals[0]["is_triggered"] is True


@pytest.mark.asyncio
async def test_evidence_tools_registry_integration(
    sample_dossier: EvidenceDossier, sample_ad_records: tuple[NormalizedAdRecord, ...]
) -> None:
    """Verify registration and schema generation for all three evidence tools in ToolRegistry."""
    registry = ToolRegistry()

    tool_metrics = GetCampaignMetricsTool(dossier_or_campaigns=sample_dossier)
    tool_history = GetHistoricalPerformanceTool(records=sample_ad_records, target_date="2026-09-03")
    tool_quality = InspectDataQualityTool(dossier_or_campaigns=sample_dossier)

    registry.register(tool_metrics)
    registry.register(tool_history)
    registry.register(tool_quality)

    assert len(registry.list_tools()) == 3

    # Dispatch via registry
    res = await registry.execute("get_campaign_metrics", campaign_name="US_Search_Brand")
    assert res.success is True

    declarations = registry.get_function_declarations()
    assert len(declarations) == 3
    names = {d["name"] for d in declarations}
    assert names == {
        "get_campaign_metrics",
        "get_historical_performance",
        "inspect_data_quality",
    }


@pytest.mark.asyncio
async def test_evidence_tools_exception_handling() -> None:
    """Verify tool execute methods catch unexpected runtime exceptions safely."""

    class BrokenCampaign:
        @property
        def campaign_name(self) -> str:
            raise RuntimeError("Campaign property error")

    broken_campaign = BrokenCampaign()
    # Pass sequence with broken campaign object
    tool_metrics = GetCampaignMetricsTool(dossier_or_campaigns=[broken_campaign])  # type: ignore[arg-type]
    res1 = await tool_metrics.execute(campaign_name="any")
    assert res1.success is False
    assert "Campaign property error" in str(res1.error)

    class BrokenRecord:
        @property
        def campaign_name(self) -> str:
            raise RuntimeError("Record property error")

    broken_record = BrokenRecord()
    tool_history = GetHistoricalPerformanceTool(records=[broken_record], target_date="2026-09-03")  # type: ignore[arg-type]
    res2 = await tool_history.execute(campaign_name="any")
    assert res2.success is False
    assert "Record property error" in str(res2.error)

    tool_quality = InspectDataQualityTool(dossier_or_campaigns=[broken_campaign])  # type: ignore[arg-type]
    res3 = await tool_quality.execute(campaign_name="any")
    assert res3.success is False
    assert "Campaign property error" in str(res3.error)
