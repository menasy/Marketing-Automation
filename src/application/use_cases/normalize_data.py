from collections.abc import Sequence
from dataclasses import dataclass

from src.application.dto.normalization_result import NormalizationResult
from src.application.ports.currency_provider import ICurrencyProvider
from src.application.ports.data_source import IDataReader
from src.application.ports.normalizer import INormalizer
from src.domain.models.ad_record import NormalizedAdRecord
from src.infrastructure.data.normalization.grain_aggregator import GrainAggregator


@dataclass(frozen=True, slots=True)
class DataSourceConfig:
    """Configuration mapping a data source file path to its specific reader and normalizer."""

    file_path: str
    reader: IDataReader
    normalizer: INormalizer


class NormalizeDataUseCase:
    """Use case for ingesting, normalizing, converting currency, and aggregating ad records."""

    def __init__(
        self,
        currency_provider: ICurrencyProvider,
        grain_aggregator: GrainAggregator | None = None,
        target_currency: str = "USD",
    ) -> None:
        """Initializes the use case with injected ports and services."""
        self._currency_provider = currency_provider
        self._grain_aggregator = grain_aggregator or GrainAggregator()
        self._target_currency = target_currency.strip().upper()

    def execute(self, sources: Sequence[DataSourceConfig]) -> NormalizationResult:
        """Executes full normalization pipeline across configured data sources.

        Args:
            sources: Sequence of DataSourceConfig items containing file paths,
                readers, and normalizers.

        Returns:
            NormalizationResult containing unified canonical records and execution audit metrics.
        """
        total_raw_records_read = 0
        all_normalized_records: list[NormalizedAdRecord] = []

        for source in sources:
            raw_records = source.reader.read(source.file_path)
            total_raw_records_read += len(raw_records)

            norm_records = source.normalizer.normalize(raw_records)

            for rec in norm_records:
                converted_rec = self._convert_currency(rec)
                all_normalized_records.append(converted_rec)

        # Aggregate records to canonical grain
        # (1 row = 1 platform x 1 campaign x 1 country x 1 date)
        aggregated_records = self._grain_aggregator.aggregate(all_normalized_records)

        # Deterministic sorting by date, platform, campaign_name, country
        sorted_records = sorted(
            aggregated_records,
            key=lambda r: (r.date, r.platform.value, r.campaign_name, r.country),
        )

        # Build platform summary breakdown
        summary_by_platform: dict[str, int] = {}
        for rec in sorted_records:
            platform_str = str(rec.platform.value)
            summary_by_platform[platform_str] = summary_by_platform.get(platform_str, 0) + 1

        skipped_records_count = max(0, total_raw_records_read - len(all_normalized_records))

        return NormalizationResult(
            records=sorted_records,
            total_raw_records_read=total_raw_records_read,
            skipped_records_count=skipped_records_count,
            summary_by_platform=summary_by_platform,
        )

    def _convert_currency(self, record: NormalizedAdRecord) -> NormalizedAdRecord:
        if record.currency.strip().upper() == self._target_currency:
            return record

        converted_spend = self._currency_provider.convert(
            record.spend, record.currency, self._target_currency, record.date
        )
        converted_val = self._currency_provider.convert(
            record.conversion_value, record.currency, self._target_currency, record.date
        )

        # Recalculate derived metrics with converted spend & conversion value
        cpc = (converted_spend / record.clicks) if record.clicks > 0 else None
        cpm = ((converted_spend / record.impressions) * 1000.0) if record.impressions > 0 else None
        cpa = (converted_spend / record.conversions) if record.conversions > 0 else None
        roas = (converted_val / converted_spend) if converted_spend > 0 else None

        return NormalizedAdRecord(
            date=record.date,
            platform=record.platform,
            campaign_name=record.campaign_name,
            country=record.country,
            currency=self._target_currency,
            spend=converted_spend,
            impressions=record.impressions,
            clicks=record.clicks,
            conversions=record.conversions,
            conversion_value=converted_val,
            ctr=record.ctr,
            cpc=cpc,
            cpm=cpm,
            cpa=cpa,
            roas=roas,
        )
