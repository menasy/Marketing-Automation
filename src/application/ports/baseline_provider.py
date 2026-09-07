from datetime import date
from typing import Protocol

from src.domain.models.ad_record import NormalizedAdRecord
from src.domain.models.metric import BaselineMetric, CurrentMetric


class IBaselineProvider(Protocol):
    """Protocol port contract for calculating historical baselines and current metrics."""

    def calculate_baselines(
        self,
        records: list[NormalizedAdRecord],
        target_date: date | str,
        window_days: int = 14,
    ) -> list[BaselineMetric]:
        """Compute rolling baseline statistics for historical slice [D - N, D - 1]."""
        ...

    def extract_current_metrics(
        self,
        records: list[NormalizedAdRecord],
        target_date: date | str,
    ) -> list[CurrentMetric]:
        """Extract current metrics observed on target date D."""
        ...

    def get_baseline_and_current(
        self,
        records: list[NormalizedAdRecord],
        target_date: date | str,
        window_days: int = 14,
    ) -> tuple[list[BaselineMetric], list[CurrentMetric]]:
        """Compute rolling baseline statistics and extract current metrics for target date D."""
        ...
