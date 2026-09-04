"""Use case implementation for statistical anomaly detection and JSON export."""

import json
from collections import defaultdict
from pathlib import Path

from src.application.dto.anomaly_dto import AnomalyDTO
from src.application.ports.anomaly_detector import IAnomalyDetector
from src.domain.enums.metric_type import MetricType
from src.domain.models.ad_record import NormalizedAdRecord
from src.domain.models.anomaly import AnomalyItem
from src.domain.services.anomaly_policy import (
    get_metric_direction,
    is_adverse_change,
    is_volume_significant,
)
from src.infrastructure.anomaly.percentage_change import (
    calculate_percentage_change,
)
from src.infrastructure.anomaly.severity import (
    classify_severity,
    generate_rationale,
)
from src.infrastructure.anomaly.z_score import calculate_z_score


class DetectAnomaliesUseCase(IAnomalyDetector):
    """Detects statistical anomalies across normalized advertising records.

    Exports results to output/anomalies.json.
    """

    def __init__(self, output_path: str = "output/anomalies.json") -> None:
        self._output_path = output_path

    def detect(self, records: list[NormalizedAdRecord], window_days: int = 14) -> list[AnomalyItem]:
        """Detect statistical anomalies using historical baseline window protection."""
        if not records:
            self._write_export([])
            return []

        # Group records by campaign key (platform, campaign_name, country)
        grouped_records: dict[tuple[str, str, str], list[NormalizedAdRecord]] = defaultdict(list)
        for r in records:
            platform_str = str(r.platform.value if hasattr(r.platform, "value") else r.platform)
            key = (platform_str, r.campaign_name, r.country)
            grouped_records[key].append(r)

        detected_anomalies: list[AnomalyItem] = []

        for (
            _platform_str,
            campaign_name,
            country,
        ), campaign_records in grouped_records.items():
            # Sort records chronologically by date
            sorted_records = sorted(campaign_records, key=lambda x: x.date)
            if not sorted_records:
                continue

            # Latest record is target date D
            current_record = sorted_records[-1]

            # Baseline slice: records strictly prior to target date D
            baseline_records = [r for r in sorted_records[:-1] if r.date < current_record.date]
            baseline_slice = baseline_records[-window_days:]

            if len(baseline_slice) < 7:
                continue

            # Compute historical baseline conversion stats for volume guard
            baseline_conversions_list = [
                r.conversions for r in baseline_slice if r.conversions is not None
            ]
            baseline_conversions_mean = (
                sum(baseline_conversions_list) / len(baseline_conversions_list)
                if baseline_conversions_list
                else 0.0
            )

            current_impressions = current_record.impressions or 0
            current_spend = current_record.spend or 0.0
            current_conversions = current_record.conversions or 0.0

            # Evaluate metrics
            metrics_to_evaluate: list[MetricType] = [
                MetricType.CPA,
                MetricType.CPC,
                MetricType.CPM,
                MetricType.ROAS,
                MetricType.CTR,
                MetricType.CONVERSIONS,
                MetricType.SPEND,
            ]

            # Check for efficiency drops (for Spend rule)
            adverse_efficiency_found = False
            for eff_metric in (
                MetricType.CPA,
                MetricType.ROAS,
                MetricType.CTR,
                MetricType.CPC,
            ):
                val = self._extract_metric_value(current_record, eff_metric)
                hist_vals = [
                    v
                    for r in baseline_slice
                    if (v := self._extract_metric_value(r, eff_metric)) is not None
                ]
                if val is not None and len(hist_vals) >= 7:
                    mean_val = sum(hist_vals) / len(hist_vals)
                    chg = calculate_percentage_change(val, mean_val)
                    if chg is not None and is_adverse_change(eff_metric, chg):
                        adverse_efficiency_found = True
                        break

            for metric_type in metrics_to_evaluate:
                current_val = self._extract_metric_value(current_record, metric_type)
                if current_val is None:
                    continue

                hist_vals = [
                    v
                    for r in baseline_slice
                    if (v := self._extract_metric_value(r, metric_type)) is not None
                ]
                sample_count = len(hist_vals)
                if sample_count < 7:
                    continue

                mean_val = sum(hist_vals) / sample_count
                var_val = sum((x - mean_val) ** 2 for x in hist_vals) / sample_count
                std_val = var_val**0.5

                # 1. Volume guard check
                if not is_volume_significant(
                    metric_type=metric_type,
                    current_impressions=float(current_impressions),
                    current_spend=current_spend,
                    current_conversions=current_conversions,
                    baseline_conversions=baseline_conversions_mean,
                ):
                    continue

                change_rate = calculate_percentage_change(current_val, mean_val)
                if change_rate is None:
                    continue

                # 2. Adverse change check
                if metric_type == MetricType.SPEND:
                    if change_rate > 0 and not adverse_efficiency_found:
                        continue
                    elif change_rate <= 0 and not is_adverse_change(metric_type, change_rate):
                        continue
                else:
                    if not is_adverse_change(metric_type, change_rate):
                        continue

                z_score = calculate_z_score(
                    current=current_val,
                    mean=mean_val,
                    std=std_val,
                    sample_count=sample_count,
                )

                # 3. Severity screening policy
                severity = classify_severity(
                    metric_type=metric_type,
                    z_score=z_score,
                    change_rate=change_rate,
                )
                if severity is None:
                    continue

                direction = get_metric_direction(metric_type)
                rationale = generate_rationale(
                    metric_type=metric_type,
                    current_value=current_val,
                    baseline_value=mean_val,
                    change_rate=change_rate,
                    z_score=z_score,
                    severity=severity,
                )

                anomaly = AnomalyItem(
                    campaign_name=campaign_name,
                    platform=current_record.platform,
                    country=country,
                    metric=metric_type,
                    current_value=current_val,
                    baseline_value=mean_val,
                    change_rate=change_rate,
                    z_score=z_score if z_score is not None else 0.0,
                    severity=severity,
                    direction=direction,
                    detection_method="rolling_zscore",
                    rationale=rationale,
                )
                detected_anomalies.append(anomaly)

        self._write_export(detected_anomalies)
        return detected_anomalies

    def _extract_metric_value(
        self, record: NormalizedAdRecord, metric_type: MetricType
    ) -> float | None:
        match metric_type:
            case MetricType.SPEND:
                return record.spend
            case MetricType.IMPRESSIONS:
                return float(record.impressions) if record.impressions is not None else None
            case MetricType.CLICKS:
                return float(record.clicks) if record.clicks is not None else None
            case MetricType.CONVERSIONS:
                return record.conversions
            case MetricType.CONVERSION_VALUE:
                return record.conversion_value
            case MetricType.CTR:
                return record.ctr
            case MetricType.CPC:
                return record.cpc
            case MetricType.CPM:
                return record.cpm
            case MetricType.CPA:
                return record.cpa
            case MetricType.ROAS:
                return record.roas

    def _write_export(self, anomalies: list[AnomalyItem]) -> None:
        dtos = [AnomalyDTO.from_domain(a) for a in anomalies]
        out_path = Path(self._output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = [dto.model_dump() for dto in dtos]
        out_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
