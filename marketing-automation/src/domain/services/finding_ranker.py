"""Domain service for operational finding clustering and root-cause diagnosis."""

import math
from collections import defaultdict

from src.domain.enums.metric_type import MetricType
from src.domain.enums.operational import (
    BidAction,
    BudgetAction,
    CreativeAction,
    IssueType,
    TrackingAction,
)
from src.domain.enums.platform import Platform
from src.domain.enums.severity import Severity
from src.domain.models.anomaly import AnomalyItem
from src.domain.models.operational_finding import OperationalFinding

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
    """Pure domain service to evaluate root cause and rank campaign findings."""

    @classmethod
    def rank_findings(
        cls, anomalies: list[AnomalyItem], max_findings: int = 3
    ) -> list[OperationalFinding]:
        """Group anomalies by campaign, evaluate root cause, and rank findings.

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
        # Use first item for platform and country context
        platform: Platform = items[0].platform
        country: str = items[0].country

        # Overall severity is the highest severity among all campaign items
        overall_severity: Severity = max(
            (item.severity for item in items),
            key=lambda s: _SEVERITY_ORDER.get(s, 0),
        )

        # Determine primary metric (metric with highest severity or highest criticality)
        primary_item = cls._select_primary_item(items)
        primary_metric = primary_item.metric

        # Evaluate issue type (DATA_QUALITY vs PERFORMANCE vs MIXED)
        issue_type = cls._evaluate_issue_type(items)

        # Map action framework
        budget_act, bid_act, creative_act, tracking_act = cls._determine_actions(issue_type, items)

        # Build evidence summary and business impact
        evidence_summary = cls._build_evidence_summary(items)
        business_impact = cls._build_business_impact(issue_type, items)

        # Build human-readable metric change and concrete operational action
        metric_change = cls._build_metric_change(items)
        operational_action = cls._build_operational_action(
            issue_type, budget_act, bid_act, creative_act, tracking_act, platform
        )

        # Compute severity score
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
            operational_action=operational_action,
            budget_action=budget_act.value,
            bid_action=bid_act.value,
            creative_action=creative_act.value,
            tracking_action=tracking_act.value,
            score=score,
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
    def _evaluate_issue_type(cls, items: list[AnomalyItem]) -> IssueType:
        """Determine whether anomalies stem from DATA_QUALITY, PERFORMANCE, or MIXED causes.

        - DATA_QUALITY:
          Spend/clicks/impressions continue normally while conversions abruptly drop to zero
          or drop >90% in 24 hours. Also negative metrics or tracking loss indicators.
        - PERFORMANCE:
          Conversions drop alongside collapsing CTR and rising CPC/CPM,
          or sudden CPA spike / ROAS collapse.
        - MIXED:
          Inconclusive patterns or low-sample spikes where attribution delay is possible.
        """
        has_negative_metric = False
        has_conversion_drop_to_zero = False
        has_severe_conversion_drop = False
        has_ctr_collapse = False
        has_cost_spike = False
        has_tracking_keyword = False

        for item in items:
            # Check for negative metric values
            if item.current_value < 0 or item.baseline_value < 0:
                has_negative_metric = True

            # Check rationale/detection keywords
            r_lower = item.rationale.lower()
            tracking_kws = (
                "pixel",
                "capi",
                "gtm",
                "tracking",
                "attribution",
                "duplicate",
                "currency",
                "negative",
            )
            if any(kw in r_lower for kw in tracking_kws):
                has_tracking_keyword = True

            # Check conversion anomalies
            if item.metric in (MetricType.CONVERSIONS, MetricType.CONVERSION_VALUE):
                if item.baseline_value > 0 and item.current_value == 0:
                    has_conversion_drop_to_zero = True
                if item.change_rate <= -0.90:
                    has_severe_conversion_drop = True

            # Check CTR anomalies
            if item.metric == MetricType.CTR and item.change_rate < -0.20:
                has_ctr_collapse = True

            # Check cost metric anomalies
            is_cost_metric = item.metric in (MetricType.CPA, MetricType.CPC, MetricType.CPM)
            if is_cost_metric and item.change_rate > 0.15:
                has_cost_spike = True

        # Rule 1: Data quality flags
        if has_negative_metric or has_tracking_keyword:
            return IssueType.DATA_QUALITY

        if (has_conversion_drop_to_zero or has_severe_conversion_drop) and not has_ctr_collapse:
            return IssueType.DATA_QUALITY

        # Rule 2: Performance issue flags
        if has_ctr_collapse and (has_cost_spike or has_severe_conversion_drop or len(items) > 1):
            return IssueType.PERFORMANCE

        if has_cost_spike and not (has_conversion_drop_to_zero or has_severe_conversion_drop):
            return IssueType.PERFORMANCE

        # Rule 3: Single metric performance shifts
        has_conv_drop = has_conversion_drop_to_zero or has_severe_conversion_drop
        if not has_conv_drop and (has_ctr_collapse or has_cost_spike):
            return IssueType.PERFORMANCE

        # Fallback / inconclusive
        if has_conversion_drop_to_zero or has_severe_conversion_drop:
            return IssueType.DATA_QUALITY

        return IssueType.MIXED

    @classmethod
    def _determine_actions(
        cls, issue_type: IssueType, items: list[AnomalyItem]
    ) -> tuple[BudgetAction, BidAction, CreativeAction, TrackingAction]:
        """Map evidence to concrete, categorized operational actions."""
        if issue_type == IssueType.DATA_QUALITY:
            # Data issue: audit tracking, hold budget, do not tamper with creatives/bids
            has_gtm = any("gtm" in item.rationale.lower() for item in items)
            tracking_act = (
                TrackingAction.VERIFY_GTM_TAGS if has_gtm else TrackingAction.AUDIT_PIXEL_CAPI
            )
            return (
                BudgetAction.HOLD,
                BidAction.NO_CHANGE,
                CreativeAction.NO_ACTION,
                tracking_act,
            )

        if issue_type == IssueType.PERFORMANCE:
            has_ctr_drop = any(
                item.metric == MetricType.CTR and item.change_rate < 0 for item in items
            )
            has_cpa_spike = any(
                item.metric == MetricType.CPA and item.change_rate > 0 for item in items
            )
            has_roas_drop = any(
                item.metric == MetricType.ROAS and item.change_rate < 0 for item in items
            )

            # Creative action
            if has_ctr_drop:
                creative_act = CreativeAction.REFRESH_FATIGUED_CREATIVES
            elif any(
                item.metric == MetricType.CONVERSIONS and item.change_rate < 0 for item in items
            ):
                creative_act = CreativeAction.AUDIT_LANDING_PAGE
            else:
                creative_act = CreativeAction.RUN_A_B_TEST

            # Budget action
            if has_cpa_spike or has_roas_drop:
                budget_act = BudgetAction.DECREASE
            else:
                budget_act = BudgetAction.REALLOCATE

            # Bid action
            if has_cpa_spike or has_roas_drop:
                bid_act = BidAction.ADJUST_TARGET_CPA_ROAS
            else:
                bid_act = BidAction.NO_CHANGE

            return budget_act, bid_act, creative_act, TrackingAction.NO_ACTION

        # IssueType.MIXED
        return (
            BudgetAction.HOLD,
            BidAction.NO_CHANGE,
            CreativeAction.RUN_A_B_TEST,
            TrackingAction.NO_ACTION,
        )

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
    def _build_business_impact(cls, issue_type: IssueType, items: list[AnomalyItem]) -> str:
        """Format a domain-grounded business impact assessment."""
        if issue_type == IssueType.DATA_QUALITY:
            spend_item = next((i for i in items if i.metric == MetricType.SPEND), None)
            sp_str = f" with active spend of ${spend_item.current_value:.2f}" if spend_item else ""
            return (
                f"Abrupt conversion/attribution tracking failure detected{sp_str}. "
                "Risk of misattributed ROI and invalid automated bidding decisions."
            )

        if issue_type == IssueType.PERFORMANCE:
            cpa_item = next((i for i in items if i.metric == MetricType.CPA), None)
            ctr_item = next((i for i in items if i.metric == MetricType.CTR), None)
            impact_parts: list[str] = []
            if cpa_item:
                impact_parts.append(f"CPA increased by {cpa_item.change_rate * 100.0:.1f}%")
            if ctr_item:
                impact_parts.append(f"CTR dropped by {abs(ctr_item.change_rate * 100.0):.1f}%")
            details = (
                ", ".join(impact_parts) if impact_parts else "Ad efficiency degradation detected"
            )
            return f"Performance decline: {details}. Requires immediate optimization."

        return "Mixed performance signals detected. Potential attribution delay or emerging trend."

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

        # Max z-score magnitude (guarded against nan/inf)
        valid_z_scores = [
            abs(item.z_score)
            for item in items
            if not (math.isnan(item.z_score) or math.isinf(item.z_score))
        ]
        max_z = max(valid_z_scores, default=0.0)

        # Spend impact contribution if present
        spend_val = 0.0
        for item in items:
            if item.metric == MetricType.SPEND:
                spend_val = max(spend_val, item.current_value, item.baseline_value)

        spend_factor = min(spend_val / 100.0, 50.0)  # cap spend factor at 50 pts

        # Extra weight for data quality tracking failures on active spending campaigns
        data_quality_factor = 20.0 if issue_type == IssueType.DATA_QUALITY else 0.0

        score = (base_weight * metric_mult) + (max_z * 5.0) + spend_factor + data_quality_factor
        return round(score, 2)

    @classmethod
    def _build_metric_change(cls, items: list[AnomalyItem]) -> str:
        """Build a human-readable metric change summary for Slack/API output.

        Example: "Conversions: 140 -> 0 (-100%) | Spend: $1,200"
        """
        parts: list[str] = []
        # Prioritize conversion/revenue metrics first, then cost metrics
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

            # Format monetary metrics with $ prefix
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

    @classmethod
    def _build_operational_action(
        cls,
        issue_type: IssueType,
        budget_act: BudgetAction,
        bid_act: BidAction,
        creative_act: CreativeAction,
        tracking_act: TrackingAction,
        platform: Platform,
    ) -> str:
        """Build a concrete, non-generic Turkish operational action sentence."""
        if issue_type == IssueType.DATA_QUALITY:
            platform_label = "Meta" if platform == Platform.META_ADS else "Google Ads"
            if tracking_act == TrackingAction.VERIFY_GTM_TAGS:
                return (
                    f"{platform_label} GTM etiketlerini doğrulayın, "
                    "dönüşüm etiketinin tetiklendiğini kontrol edin. "
                    "Bütçeyi kapatmayın — veri sorunu çözülene kadar bekleyin."
                )
            return (
                f"{platform_label} CAPI/Pixel entegrasyonunu kontrol edin, "
                "Event Manager'da son 24 saat etkinlik akışını doğrulayın. "
                "Bütçeyi kapatmayın — tracking düzeltilmeden performans değerlendirmesi yapılamaz."
            )

        if issue_type == IssueType.PERFORMANCE:
            action_parts: list[str] = []
            if budget_act == BudgetAction.DECREASE:
                action_parts.append("Günlük bütçeyi %20 kısın")
            elif budget_act == BudgetAction.REALLOCATE:
                action_parts.append(
                    "Bütçeyi düşük performanslı kampanyadan yüksek ROAS'lı kampanyaya aktarın"
                )

            if bid_act == BidAction.ADJUST_TARGET_CPA_ROAS:
                action_parts.append("hedef CPA/ROAS teklifini güncelleyin")

            if creative_act == CreativeAction.REFRESH_FATIGUED_CREATIVES:
                action_parts.append("yıpranmış kreatifleri yenileyin")
            elif creative_act == CreativeAction.AUDIT_LANDING_PAGE:
                action_parts.append("açılış sayfasını denetleyin")
            elif creative_act == CreativeAction.RUN_A_B_TEST:
                action_parts.append("yeni kreatiflerle A/B testi başlatın")

            if platform == Platform.GOOGLE_ADS:
                action_parts.append("negatif keyword listesini gözden geçirin")

            return (
                ", ".join(action_parts) + "."
                if action_parts
                else (
                    "Kampanya performansını izlemeye devam edin, "
                    "24 saat içinde trend devam ederse bütçe müdahalesi uygulayın."
                )
            )

        # MIXED
        return (
            "24-48 saat izlemeye devam edin — atıf gecikme ihtimali var. "
            "Trend devam ederse bütçe ve tracking denetimi başlatın."
        )
