"""Pure domain service for evaluating objective data quality and metric irregularity signals."""

from src.domain.enums.metric_type import MetricType
from src.domain.models.anomaly import AnomalyItem
from src.domain.models.data_quality_signal import DataQualitySignal, DataQualitySignalType


class DataQualityAnalyzer:
    """Pure domain service that extracts objective data quality signals from anomaly items.

    Strictly factual: contains zero diagnostic assertions ("tracking hatası", "piksel kopması")
    and zero operational action recommendations ("bütçeyi kısın").
    """

    @classmethod
    def analyze_campaign_signals(cls, anomalies: list[AnomalyItem]) -> list[DataQualitySignal]:
        """Analyze a list of campaign anomalies and return DataQualitySignal objects.

        Args:
            anomalies: List of AnomalyItem instances for a single campaign.

        Returns:
            List of DataQualitySignal objects evaluating objective metric conditions.
        """
        if not anomalies:
            return []

        signals: list[DataQualitySignal] = []

        # Index anomaly items by metric type for fast factual cross-examination
        by_metric: dict[MetricType, AnomalyItem] = {item.metric: item for item in anomalies}

        # 1. ZERO_CONVERSIONS_WITH_ACTIVE_SPEND
        spend_item = by_metric.get(MetricType.SPEND)
        conv_item = by_metric.get(MetricType.CONVERSIONS)
        conv_val_item = by_metric.get(MetricType.CONVERSION_VALUE)

        active_spend = spend_item.current_value if spend_item else 0.0
        target_conv_item = conv_item or conv_val_item

        if active_spend > 50.0 and target_conv_item:
            if target_conv_item.baseline_value > 0.0 and target_conv_item.current_value == 0.0:
                conv_name = target_conv_item.metric.value.upper()
                c_base = target_conv_item.baseline_value
                signals.append(
                    DataQualitySignal(
                        signal_type=DataQualitySignalType.ZERO_CONVERSIONS_WITH_ACTIVE_SPEND,
                        is_triggered=True,
                        metric_name=conv_name,
                        current_value=target_conv_item.current_value,
                        baseline_value=c_base,
                        delta_pct=-100.0,
                        factual_statement=(
                            f"Active spend (${active_spend:,.2f}) observed while {conv_name} "
                            f"dropped from {c_base:,.2f} to 0.00 (-100.0%)."
                        ),
                    )
                )

        # 2. CTR_STABLE_CONV_COLLAPSE
        ctr_item = by_metric.get(MetricType.CTR)
        if ctr_item and target_conv_item:
            ctr_stable = ctr_item.change_rate > -0.15
            conv_collapsed = target_conv_item.change_rate <= -0.50
            if ctr_stable and conv_collapsed:
                ctr_pct = ctr_item.change_rate * 100.0
                conv_pct = target_conv_item.change_rate * 100.0
                m_name = target_conv_item.metric.value.upper()
                signals.append(
                    DataQualitySignal(
                        signal_type=DataQualitySignalType.CTR_STABLE_CONV_COLLAPSE,
                        is_triggered=True,
                        metric_name=m_name,
                        current_value=target_conv_item.current_value,
                        baseline_value=target_conv_item.baseline_value,
                        delta_pct=conv_pct,
                        factual_statement=(
                            f"CTR change is stable ({ctr_pct:+.1f}%) while "
                            f"{m_name} changed by {conv_pct:.1f}%."
                        ),
                    )
                )

        # 3. COST_SPIKE_VOLUME_DROP
        cpa_item = by_metric.get(MetricType.CPA)
        impressions_item = by_metric.get(MetricType.IMPRESSIONS)
        clicks_item = by_metric.get(MetricType.CLICKS)

        volume_item = impressions_item or clicks_item
        volume_stable_or_up = volume_item and volume_item.change_rate >= 0.0

        if spend_item and cpa_item and volume_stable_or_up:
            if spend_item.change_rate > 0.40 and cpa_item.change_rate > 0.50:
                spend_pct = spend_item.change_rate * 100.0
                cpa_pct = cpa_item.change_rate * 100.0
                signals.append(
                    DataQualitySignal(
                        signal_type=DataQualitySignalType.COST_SPIKE_VOLUME_DROP,
                        is_triggered=True,
                        metric_name="CPA",
                        current_value=cpa_item.current_value,
                        baseline_value=cpa_item.baseline_value,
                        delta_pct=cpa_pct,
                        factual_statement=(
                            f"Spend increased by {spend_pct:+.1f}% and CPA spiked "
                            f"by {cpa_pct:+.1f}% while ad volume was stable or increased."
                        ),
                    )
                )

        # 4. NEGATIVE_OR_ZERO_METRIC
        for item in anomalies:
            if item.current_value < 0.0 or item.baseline_value < 0.0:
                m_name = item.metric.value.upper()
                c_val = item.current_value
                b_val = item.baseline_value
                signals.append(
                    DataQualitySignal(
                        signal_type=DataQualitySignalType.NEGATIVE_OR_ZERO_METRIC,
                        is_triggered=True,
                        metric_name=m_name,
                        current_value=c_val,
                        baseline_value=b_val,
                        delta_pct=item.change_rate * 100.0,
                        factual_statement=(
                            f"Negative metric value detected: {m_name} "
                            f"(current: {c_val:.2f}, baseline: {b_val:.2f})."
                        ),
                    )
                )

        # 5. UNUSUAL_VOLUME_SURGE
        for vol_item in [i for i in (impressions_item, clicks_item) if i is not None]:
            if vol_item.change_rate > 2.0 and vol_item.z_score > 4.0:
                change_pct = vol_item.change_rate * 100.0
                m_name = vol_item.metric.value.upper()
                signals.append(
                    DataQualitySignal(
                        signal_type=DataQualitySignalType.UNUSUAL_VOLUME_SURGE,
                        is_triggered=True,
                        metric_name=m_name,
                        current_value=vol_item.current_value,
                        baseline_value=vol_item.baseline_value,
                        delta_pct=change_pct,
                        factual_statement=(
                            f"Unusual volume surge in {m_name}: "
                            f"{vol_item.baseline_value:,.0f} to {vol_item.current_value:,.0f} "
                            f"(+{change_pct:.1f}%, z-score: {vol_item.z_score:.2f})."
                        ),
                    )
                )

        return signals
