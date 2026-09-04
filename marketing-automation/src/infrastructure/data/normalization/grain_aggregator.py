import math
from collections import defaultdict

from src.domain.enums.platform import Platform
from src.domain.models.ad_record import NormalizedAdRecord


class GrainAggregator:
    """Utility for aggregating NormalizedAdRecord items to canonical grain.

    Canonical Grain: 1 row = 1 platform × 1 campaign_name × 1 country × 1 date.
    Aggregates additive metrics (spend, impressions, clicks, conversions, conversion_value)
    and recalculates derived metrics defensively.
    """

    def aggregate(self, records: list[NormalizedAdRecord]) -> list[NormalizedAdRecord]:
        """Aggregates a list of NormalizedAdRecord instances into unique canonical grain rows.

        Args:
            records: List of normalized ad records (potentially containing split breakdown rows).

        Returns:
            List of aggregated NormalizedAdRecord instances guaranteed to have
            unique composite keys.
        """
        if not records:
            return []

        # Group records by (platform, campaign_name, country, date)
        grouped_records: dict[tuple[Platform, str, str, str], list[NormalizedAdRecord]] = (
            defaultdict(list)
        )

        for rec in records:
            composite_key = (rec.platform, rec.campaign_name, rec.country, rec.date)
            grouped_records[composite_key].append(rec)

        aggregated_records: list[NormalizedAdRecord] = []

        for (platform, campaign_name, country, date_str), group in grouped_records.items():
            if len(group) == 1:
                aggregated_records.append(group[0])
                continue

            # Sum additive volume metrics across group
            total_spend = sum(r.spend for r in group)
            total_impressions = sum(r.impressions for r in group)
            total_clicks = sum(r.clicks for r in group)
            total_conversions = sum(r.conversions for r in group)
            total_conversion_value = sum(r.conversion_value for r in group)
            currency = group[0].currency

            # Recalculate derived metrics defensively
            ctr = (total_clicks / total_impressions) if total_impressions > 0 else None
            cpc = (total_spend / total_clicks) if total_clicks > 0 else None
            cpm = ((total_spend / total_impressions) * 1000.0) if total_impressions > 0 else None
            cpa = (total_spend / total_conversions) if total_conversions > 0 else None
            roas = (total_conversion_value / total_spend) if total_spend > 0 else None

            # Sanitize float values
            ctr = self._sanitize_float(ctr)
            cpc = self._sanitize_float(cpc)
            cpm = self._sanitize_float(cpm)
            cpa = self._sanitize_float(cpa)
            roas = self._sanitize_float(roas)

            aggregated_rec = NormalizedAdRecord(
                date=date_str,
                platform=platform,
                campaign_name=campaign_name,
                country=country,
                currency=currency,
                spend=total_spend,
                impressions=total_impressions,
                clicks=total_clicks,
                conversions=total_conversions,
                conversion_value=total_conversion_value,
                ctr=ctr,
                cpc=cpc,
                cpm=cpm,
                cpa=cpa,
                roas=roas,
            )
            aggregated_records.append(aggregated_rec)

        return aggregated_records

    def _sanitize_float(self, val: float | None) -> float | None:
        if val is None:
            return None
        if math.isnan(val) or math.isinf(val):
            return None
        return val
