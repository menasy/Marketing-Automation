"""Pure domain service for compiling evidence dossiers from anomalies and ad records."""

import math
from collections import defaultdict

from src.domain.enums.metric_type import MetricType
from src.domain.models.ad_record import NormalizedAdRecord
from src.domain.models.anomaly import AnomalyItem
from src.domain.models.evidence_dossier import (
    CampaignEvidence,
    EvidenceDossier,
    MetricEvidence,
)
from src.domain.services.data_quality import DataQualityAnalyzer

STANDARD_FUNNEL_METRICS: tuple[str, ...] = (
    "SPEND",
    "IMPRESSIONS",
    "CLICKS",
    "CTR",
    "CPC",
    "CONVERSIONS",
    "CPA",
    "ROAS",
)


class DossierCompiler:
    """Pure domain service that clusters multi-metric anomalies into a structured EvidenceDossier.

    Strictly factual: performs zero subjective text generation or diagnostic claims.
    """

    @classmethod
    def compile_dossier(
        cls,
        anomalies: list[AnomalyItem],
        records: list[NormalizedAdRecord] | None = None,
        target_date: str = "",
        baseline_window: str = "",
        max_campaigns: int = 3,
    ) -> EvidenceDossier:
        """Compile detected anomaly items and normalized records into an EvidenceDossier.

        Args:
            anomalies: List of detected AnomalyItem instances across campaigns.
            records: Optional list of current target date NormalizedAdRecord entities.
            target_date: ISO target date string (e.g. '2026-09-03').
            baseline_window: Range description string (e.g. '2026-08-05 to 2026-09-02').
            max_campaigns: Maximum top impact campaign cases to include in top_campaign_evidence.

        Returns:
            Immutable EvidenceDossier entity.
        """
        if not anomalies:
            return EvidenceDossier(
                target_date=target_date,
                baseline_window=baseline_window,
                total_anomalies_detected=0,
                total_campaigns_impacted=0,
                top_campaign_evidence=(),
            )

        # 1. Group anomalies by campaign name
        campaign_anomalies: dict[str, list[AnomalyItem]] = defaultdict(list)
        for item in anomalies:
            campaign_anomalies[item.campaign_name].append(item)

        # 2. Index records by campaign name for baseline fill
        campaign_records: dict[str, NormalizedAdRecord] = {}
        if records:
            for rec in records:
                campaign_records[rec.campaign_name] = rec

        # 3. Build CampaignEvidence for each impacted campaign
        all_evidences: list[CampaignEvidence] = []
        for c_name, c_items in campaign_anomalies.items():
            record = campaign_records.get(c_name)
            evidence = cls._build_campaign_evidence(c_name, c_items, record)
            all_evidences.append(evidence)

        # 4. Rank campaigns by financial_impact_score descending
        all_evidences.sort(key=lambda e: e.financial_impact_score, reverse=True)

        top_evidences = tuple(all_evidences[:max_campaigns])

        return EvidenceDossier(
            target_date=target_date,
            baseline_window=baseline_window,
            total_anomalies_detected=len(anomalies),
            total_campaigns_impacted=len(campaign_anomalies),
            top_campaign_evidence=top_evidences,
        )

    @classmethod
    def _build_campaign_evidence(
        cls,
        campaign_name: str,
        items: list[AnomalyItem],
        record: NormalizedAdRecord | None,
    ) -> CampaignEvidence:
        """Build a single CampaignEvidence domain entity."""
        first_item = items[0]
        platform_str = (
            first_item.platform.value
            if hasattr(first_item.platform, "value")
            else str(first_item.platform)
        )
        country_str = first_item.country

        # Account ID / Campaign ID defaults if not in anomaly item
        campaign_id = campaign_name.lower().replace(" ", "_")
        account_id = f"act_{platform_str.lower()}_{country_str.lower()}"

        # Current spend extraction
        spend_val = 0.0
        spend_anomaly = next((i for i in items if i.metric == MetricType.SPEND), None)
        if spend_anomaly:
            spend_val = spend_anomaly.current_value
        elif record:
            spend_val = record.spend

        # Financial risk score calculation: Spend * max(|Z_CPA|, |Z_Spend|, |Z_Conv|)
        impact_score = cls._calculate_financial_impact_score(spend_val, items)

        # Extract data quality signals
        signals = DataQualityAnalyzer.analyze_campaign_signals(items)

        # Compile complete 8-metric table
        metrics_table = cls._compile_metrics_table(items, record)

        return CampaignEvidence(
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            platform=platform_str,
            account_id=account_id,
            country=country_str,
            spend=spend_val,
            financial_impact_score=impact_score,
            metrics=metrics_table,
            data_quality_signals=tuple(signals),
        )

    @classmethod
    def _calculate_financial_impact_score(cls, spend: float, items: list[AnomalyItem]) -> float:
        """Calculate financial risk score: Spend * max(|Z_CPA|, |Z_Spend|, |Z_Conv|)."""
        target_metrics = (
            MetricType.CPA,
            MetricType.SPEND,
            MetricType.CONVERSIONS,
            MetricType.CONVERSION_VALUE,
        )

        relevant_z_scores: list[float] = []
        fallback_deltas: list[float] = []

        for item in items:
            z = item.z_score
            if not (math.isnan(z) or math.isinf(z)):
                if item.metric in target_metrics:
                    relevant_z_scores.append(abs(z))
                else:
                    relevant_z_scores.append(abs(z) * 0.8)

            delta = item.change_rate
            if not (math.isnan(delta) or math.isinf(delta)):
                fallback_deltas.append(abs(delta))

        if relevant_z_scores:
            max_multiplier = max(relevant_z_scores)
        elif fallback_deltas:
            max_multiplier = max(fallback_deltas)
        else:
            max_multiplier = 1.0

        return round(spend * max_multiplier, 2)

    @classmethod
    def _compile_metrics_table(
        cls, items: list[AnomalyItem], record: NormalizedAdRecord | None
    ) -> dict[str, MetricEvidence]:
        """Compile a complete, non-truncated 8-metric table for the campaign."""
        metric_anomalies: dict[str, AnomalyItem] = {}
        for item in items:
            metric_anomalies[item.metric.value.upper()] = item

        metrics_table: dict[str, MetricEvidence] = {}

        for m_name in STANDARD_FUNNEL_METRICS:
            if m_name in metric_anomalies:
                anom = metric_anomalies[m_name]
                c_val = anom.current_value
                b_val = anom.baseline_value
                z = anom.z_score
                delta = anom.change_rate * 100.0 if not math.isnan(anom.change_rate) else None
                metrics_table[m_name] = MetricEvidence(
                    metric_name=m_name,
                    current_value=c_val if not math.isnan(c_val) else None,
                    baseline_value=b_val if not math.isnan(b_val) else None,
                    delta_pct=round(delta, 2) if delta is not None else None,
                    z_score=round(z, 2) if not math.isnan(z) else None,
                    is_anomaly=True,
                )
            else:
                raw_val = cls._extract_value_from_record(m_name, record)
                c_val_clean = raw_val if (raw_val is not None and not math.isnan(raw_val)) else None
                metrics_table[m_name] = MetricEvidence(
                    metric_name=m_name,
                    current_value=c_val_clean,
                    baseline_value=None,
                    delta_pct=None,
                    z_score=None,
                    is_anomaly=False,
                )

        return metrics_table

    @staticmethod
    def _extract_value_from_record(
        metric_name: str, record: NormalizedAdRecord | None
    ) -> float | None:
        """Extract current value for a metric from record if available."""
        if not record:
            return None

        m_upper = metric_name.upper()
        if m_upper == "SPEND":
            return record.spend
        if m_upper == "IMPRESSIONS":
            return float(record.impressions)
        if m_upper == "CLICKS":
            return float(record.clicks)
        if m_upper == "CTR":
            return record.ctr
        if m_upper == "CPC":
            return record.cpc
        if m_upper == "CONVERSIONS":
            return record.conversions
        if m_upper == "CPA":
            return record.cpa
        if m_upper == "ROAS":
            return record.roas

        return None
