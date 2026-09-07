"""Domain service for operational finding clustering and score evaluation."""

import math
from collections import defaultdict

from src.domain.enums.metric_type import MetricType
from src.domain.enums.operational import IssueType
from src.domain.enums.platform import Platform
from src.domain.enums.severity import Severity
from src.domain.models.anomaly import AnomalyItem
from src.domain.models.data_quality_signal import DataQualitySignal, DataQualitySignalType
from src.domain.models.operational_finding import OperationalFinding
from src.domain.services.data_quality import DataQualityAnalyzer

_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 3,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
}

_SEVERITY_WEIGHTS: dict[Severity, float] = {
    Severity.CRITICAL: 100.0,
    Severity.HIGH: 75.0,
    Severity.MEDIUM: 50.0,
    Severity.LOW: 25.0,
}

_METRIC_CRITICALITY_MULTIPLIER: dict[MetricType, float] = {
    MetricType.CONVERSIONS: 1.5,
    MetricType.CONVERSION_VALUE: 1.5,
    MetricType.ROAS: 1.5,
    MetricType.CPA: 1.5,
    MetricType.CTR: 1.2,
    MetricType.CPC: 1.2,
    MetricType.CPM: 1.2,
    MetricType.SPEND: 1.0,
    MetricType.CLICKS: 1.0,
    MetricType.IMPRESSIONS: 1.0,
}


class FindingRanker:
    """Pure domain service to cluster anomalies and score campaign findings.

    Contains zero hardcoded diagnostic keyword matching or rule-based recommendations.
    """

    @classmethod
    def rank_findings(
        cls, anomalies: list[AnomalyItem], max_findings: int = 3
    ) -> list[OperationalFinding]:
        """Group anomalies by campaign, extract data quality signals, and rank findings.

        Args:
            anomalies: List of statistical anomaly items detected across campaigns.
            max_findings: Maximum number of ranked items to return (default 3).

        Returns:
            List of top-N OperationalFinding items ordered by score descending.
        """
        if not anomalies:
            return []

        # 1. Group anomaly items by campaign name
        campaign_groups: dict[str, list[AnomalyItem]] = defaultdict(list)
        for item in anomalies:
            campaign_groups[item.campaign_name].append(item)

        findings: list[OperationalFinding] = []
        for campaign_name, items in campaign_groups.items():
            finding = cls._create_finding(campaign_name, items)
            findings.append(finding)

        # 2. Sort by score descending
        findings.sort(key=lambda f: f.score, reverse=True)

        # 3. Return top max_findings
        return findings[:max_findings]

    @classmethod
    def _create_finding(cls, campaign_name: str, items: list[AnomalyItem]) -> OperationalFinding:
        """Evaluate a campaign's anomaly items to produce a single unified OperationalFinding."""
        platform: Platform = items[0].platform
        country: str = items[0].country

        overall_severity: Severity = max(
            (item.severity for item in items),
            key=lambda s: _SEVERITY_ORDER.get(s, 0),
        )

        primary_item = cls._select_primary_item(items)
        primary_metric = primary_item.metric

        # Extract objective data quality signals using DataQualityAnalyzer
        signals = DataQualityAnalyzer.analyze_campaign_signals(items)

        # Classify issue_type purely based on objective signals
        issue_type = cls._classify_issue_type_from_signals(signals, items)

        evidence_summary = cls._build_evidence_summary(items)
        business_impact = cls._build_business_impact(items)
        metric_change = cls._build_metric_change(items)

        score = cls._calculate_score(overall_severity, primary_metric, items, issue_type)

        return OperationalFinding(
            campaign_name=campaign_name,
            platform=platform,
            country=country,
            primary_metric=primary_metric,
            severity=overall_severity,
            issue_type=issue_type,
            evidence_summary=evidence_summary,
            business_impact=business_impact,
            metric_change=metric_change,
            score=score,
            data_quality_signals=tuple(signals),
        )

    @classmethod
    def _select_primary_item(cls, items: list[AnomalyItem]) -> AnomalyItem:
        """Select the primary anomaly item based on severity and metric criticality."""

        def _sort_key(item: AnomalyItem) -> tuple[int, float, float]:
            z = (
                abs(item.z_score)
                if not (math.isnan(item.z_score) or math.isinf(item.z_score))
                else 0.0
            )
            return (
                _SEVERITY_ORDER.get(item.severity, 0),
                _METRIC_CRITICALITY_MULTIPLIER.get(item.metric, 1.0),
                z,
            )

        return max(items, key=_sort_key)

    @classmethod
    def _classify_issue_type_from_signals(
        cls, signals: list[DataQualitySignal], items: list[AnomalyItem]
    ) -> IssueType:
        """Classify IssueType purely from objective signals without text search."""
        has_dq_signal = any(
            s.signal_type
            in (
                DataQualitySignalType.ZERO_CONVERSIONS_WITH_ACTIVE_SPEND,
                DataQualitySignalType.NEGATIVE_OR_ZERO_METRIC,
                DataQualitySignalType.CTR_STABLE_CONV_COLLAPSE,
            )
            and s.is_triggered
            for s in signals
        )

        if has_dq_signal:
            return IssueType.DATA_QUALITY

        has_ctr_drop = any(i.metric == MetricType.CTR and i.change_rate < 0 for i in items)
        has_cost_spike = any(
            i.metric in (MetricType.CPA, MetricType.CPC, MetricType.CPM) and i.change_rate > 0
            for i in items
        )

        if has_ctr_drop or has_cost_spike:
            return IssueType.PERFORMANCE

        return IssueType.MIXED

    @classmethod
    def _build_evidence_summary(cls, items: list[AnomalyItem]) -> str:
        """Format a clear, evidence-based summary of all anomalies in this campaign finding."""
        summaries: list[str] = []
        for item in items:
            change_pct = item.change_rate * 100.0
            sign = "+" if change_pct > 0 else ""
            m_str = item.metric.value.upper()
            curr = item.current_value
            base = item.baseline_value
            z = item.z_score
            summaries.append(
                f"{m_str} changed by {sign}{change_pct:.1f}% "
                f"(current: {curr:.2f}, baseline: {base:.2f}, z-score: {z:.2f})"
            )
        return " | ".join(summaries)

    @classmethod
    def _build_business_impact(cls, items: list[AnomalyItem]) -> str:
        """Format an objective numerical business impact summary without subjective claims."""
        spend_item = next((i for i in items if i.metric == MetricType.SPEND), None)
        spend_str = f"${spend_item.current_value:,.2f}" if spend_item else "N/A"

        anomalous_metrics = [i.metric.value.upper() for i in items]
        metrics_str = ", ".join(anomalous_metrics)

        return (
            f"Campaign active spend: {spend_str}. "
            f"Detected statistical anomalies across {len(items)} metric(s): {metrics_str}."
        )

    @classmethod
    def _calculate_score(
        cls,
        severity: Severity,
        primary_metric: MetricType,
        items: list[AnomalyItem],
        issue_type: IssueType,
    ) -> float:
        """Calculate operational severity score."""
        base_weight = _SEVERITY_WEIGHTS.get(severity, 25.0)
        metric_mult = _METRIC_CRITICALITY_MULTIPLIER.get(primary_metric, 1.0)

        valid_z_scores = [
            abs(item.z_score)
            for item in items
            if not (math.isnan(item.z_score) or math.isinf(item.z_score))
        ]
        max_z = max(valid_z_scores, default=0.0)

        spend_val = 0.0
        for item in items:
            if item.metric == MetricType.SPEND:
                spend_val = max(spend_val, item.current_value, item.baseline_value)

        spend_factor = min(spend_val / 100.0, 50.0)
        data_quality_factor = 20.0 if issue_type == IssueType.DATA_QUALITY else 0.0

        score = (base_weight * metric_mult) + (max_z * 5.0) + spend_factor + data_quality_factor
        return round(score, 2)

    @classmethod
    def _build_metric_change(cls, items: list[AnomalyItem]) -> str:
        """Build a human-readable metric change summary."""
        parts: list[str] = []
        priority_order: list[MetricType] = [
            MetricType.CONVERSIONS,
            MetricType.CONVERSION_VALUE,
            MetricType.ROAS,
            MetricType.CPA,
            MetricType.CTR,
            MetricType.CPC,
            MetricType.CPM,
            MetricType.SPEND,
            MetricType.CLICKS,
            MetricType.IMPRESSIONS,
        ]
        sorted_items = sorted(
            items,
            key=lambda i: (
                priority_order.index(i.metric)
                if i.metric in priority_order
                else len(priority_order)
            ),
        )
        for item in sorted_items:
            change_pct = item.change_rate * 100.0
            sign = "+" if change_pct > 0 else ""
            label = item.metric.value.upper()

            if item.metric in (
                MetricType.SPEND,
                MetricType.CPA,
                MetricType.CPC,
                MetricType.CONVERSION_VALUE,
            ):
                curr_str = f"${item.current_value:,.0f}"
                base_str = f"${item.baseline_value:,.0f}"
            else:
                curr_str = f"{item.current_value:,.2f}"
                base_str = f"{item.baseline_value:,.2f}"

            parts.append(f"{label}: {base_str} → {curr_str} ({sign}{change_pct:.0f}%)")

        return " | ".join(parts)
