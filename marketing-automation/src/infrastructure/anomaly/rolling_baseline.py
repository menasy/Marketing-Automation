import math
from datetime import date, timedelta

import numpy as np

from src.application.ports.baseline_provider import IBaselineProvider
from src.domain.enums.metric_type import MetricType
from src.domain.enums.platform import Platform
from src.domain.models.ad_record import NormalizedAdRecord
from src.domain.models.metric import BaselineMetric, CurrentMetric, MetricStats
from src.domain.services.metric_calculator import MetricCalculator


class RollingBaselineEngine(IBaselineProvider):
    """Infrastructure engine computing rolling baseline statistics without look-ahead bias."""

    @staticmethod
    def _parse_date(d: date | str) -> date:
        """Parse string or date into a date object."""
        if isinstance(d, date):
            return d
        return date.fromisoformat(d)

    @classmethod
    def _extract_metric_value(
        cls, enriched_record: NormalizedAdRecord, metric_type: MetricType
    ) -> float | None:
        """Extract typed metric value from an enriched record."""
        match metric_type:
            case MetricType.SPEND:
                return enriched_record.spend
            case MetricType.IMPRESSIONS:
                return float(enriched_record.impressions)
            case MetricType.CLICKS:
                return float(enriched_record.clicks)
            case MetricType.CONVERSIONS:
                return enriched_record.conversions
            case MetricType.CONVERSION_VALUE:
                return enriched_record.conversion_value
            case MetricType.CTR:
                return enriched_record.ctr
            case MetricType.CPC:
                return enriched_record.cpc
            case MetricType.CPM:
                return enriched_record.cpm
            case MetricType.CPA:
                return enriched_record.cpa
            case MetricType.ROAS:
                return enriched_record.roas

    def calculate_baselines(
        self,
        records: list[NormalizedAdRecord],
        target_date: date | str,
        window_days: int = 14,
    ) -> list[BaselineMetric]:
        """Compute rolling baseline statistics for historical slice [D - N, D - 1].

        Target date D is strictly excluded from historical calculations to prevent look-ahead bias.
        """
        target_dt = self._parse_date(target_date)
        window_end = target_dt - timedelta(days=1)
        window_start = target_dt - timedelta(days=window_days)

        # Partition records by granularity key: (platform, campaign_name, country)
        grouped_records: dict[tuple[Platform, str, str], list[NormalizedAdRecord]] = {}
        for rec in records:
            rec_dt = self._parse_date(rec.date)
            # Strict look-ahead bias guard: include only records within [D - N, D - 1]
            if window_start <= rec_dt <= window_end:
                key = (rec.platform, rec.campaign_name, rec.country)
                grouped_records.setdefault(key, []).append(rec)

        baselines: list[BaselineMetric] = []

        for (platform, campaign_name, country), historical_recs in grouped_records.items():
            enriched_recs = [MetricCalculator.enrich_record(r) for r in historical_recs]
            metric_stats_dict: dict[MetricType, MetricStats] = {}
            group_insufficient = False

            for metric_type in MetricType:
                raw_values = [self._extract_metric_value(rec, metric_type) for rec in enriched_recs]
                valid_values = [
                    v
                    for v in raw_values
                    if v is not None and not math.isnan(v) and not math.isinf(v)
                ]
                sample_count = len(valid_values)

                if sample_count == 0:
                    is_insufficient = True
                    group_insufficient = True
                    stats = MetricStats(
                        mean=0.0,
                        std=0.0,
                        median=0.0,
                        sample_count=0,
                        min_value=0.0,
                        max_value=0.0,
                        insufficient_history=is_insufficient,
                    )
                else:
                    arr = np.array(valid_values, dtype=np.float64)
                    mean_val = float(np.mean(arr))
                    std_val = float(np.std(arr, ddof=0))
                    median_val = float(np.median(arr))
                    min_val = float(np.min(arr))
                    max_val = float(np.max(arr))
                    is_insufficient = sample_count < 7
                    if is_insufficient:
                        group_insufficient = True

                    stats = MetricStats(
                        mean=round(mean_val, 4),
                        std=round(std_val, 4),
                        median=round(median_val, 4),
                        sample_count=sample_count,
                        min_value=round(min_val, 4),
                        max_value=round(max_val, 4),
                        insufficient_history=is_insufficient,
                    )

                metric_stats_dict[metric_type] = stats

            baselines.append(
                BaselineMetric(
                    platform=platform,
                    campaign_name=campaign_name,
                    country=country,
                    window_start=window_start,
                    window_end=window_end,
                    metrics=metric_stats_dict,
                    insufficient_history=group_insufficient,
                )
            )

        return baselines

    def extract_current_metrics(
        self,
        records: list[NormalizedAdRecord],
        target_date: date | str,
    ) -> list[CurrentMetric]:
        """Extract observed metrics on target date D."""
        target_dt = self._parse_date(target_date)
        current_metrics: list[CurrentMetric] = []

        for rec in records:
            rec_dt = self._parse_date(rec.date)
            if rec_dt == target_dt:
                enriched = MetricCalculator.enrich_record(rec)
                metric_dict: dict[MetricType, float | None] = {}
                for metric_type in MetricType:
                    metric_dict[metric_type] = self._extract_metric_value(enriched, metric_type)

                current_metrics.append(
                    CurrentMetric(
                        platform=rec.platform,
                        campaign_name=rec.campaign_name,
                        country=rec.country,
                        date=target_dt,
                        metrics=metric_dict,
                    )
                )

        return current_metrics

    def get_baseline_and_current(
        self,
        records: list[NormalizedAdRecord],
        target_date: date | str,
        window_days: int = 14,
    ) -> tuple[list[BaselineMetric], list[CurrentMetric]]:
        """Compute rolling baseline statistics and extract current metrics for target date D."""
        baselines = self.calculate_baselines(records, target_date, window_days)
        currents = self.extract_current_metrics(records, target_date)
        return baselines, currents
