from dataclasses import replace
from datetime import date

from src.application.dto.baseline_dto import BaselineDatasetDTO
from src.application.ports.baseline_provider import IBaselineProvider
from src.domain.enums.metric_type import MetricType
from src.domain.enums.platform import Platform
from src.domain.models.ad_record import NormalizedAdRecord
from src.domain.models.metric import BaselineMetric, CurrentMetric


class BuildBaselineUseCase:
    """Use case orchestrating dataset splitting, auto date resolution, and baseline construction."""

    def __init__(self, baseline_provider: IBaselineProvider) -> None:
        self._baseline_provider = baseline_provider

    @staticmethod
    def _parse_date(d: date | str) -> date:
        """Parse string or date into date object."""
        if isinstance(d, date):
            return d
        return date.fromisoformat(d)

    def execute(
        self,
        records: list[NormalizedAdRecord],
        target_date: date | str | None = None,
        window_days: int = 14,
    ) -> BaselineDatasetDTO:
        """Execute baseline calculation and dataset alignment.

        If target_date is not provided, resolves target date automatically as max(record.date).
        """
        if target_date is None or (isinstance(target_date, str) and not target_date.strip()):
            if not records:
                raise ValueError("Cannot resolve target date from an empty records list.")
            resolved_dt = max(self._parse_date(r.date) for r in records)
        else:
            resolved_dt = self._parse_date(target_date)

        baselines, currents = self._baseline_provider.get_baseline_and_current(
            records=records,
            target_date=resolved_dt,
            window_days=window_days,
        )

        baseline_map: dict[tuple[Platform, str, str], BaselineMetric] = {
            (b.platform, b.campaign_name, b.country): b for b in baselines
        }

        tagged_currents: list[CurrentMetric] = []
        low_volume_count = 0

        for current in currents:
            spend = current.metrics.get(MetricType.SPEND)
            impressions = current.metrics.get(MetricType.IMPRESSIONS)

            is_low_vol = False
            if spend is None or spend <= 0 or impressions is None or impressions <= 0:
                is_low_vol = True
                low_volume_count += 1

            if current.is_low_volume != is_low_vol:
                current = replace(current, is_low_volume=is_low_vol)

            tagged_currents.append(current)

        excluded_count = sum(1 for b in baselines if b.insufficient_history)

        return BaselineDatasetDTO(
            target_date=resolved_dt,
            current_metrics=tagged_currents,
            baseline_metrics=baseline_map,
            total_campaigns_analyzed=len(tagged_currents),
            excluded_new_campaigns_count=excluded_count,
            low_volume_campaigns_count=low_volume_count,
        )
