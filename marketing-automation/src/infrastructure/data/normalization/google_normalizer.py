import math
from datetime import datetime
from typing import Any

from src.application.ports.normalizer import INormalizer
from src.domain.enums.platform import Platform
from src.domain.exceptions import NormalizationError
from src.domain.models.ad_record import NormalizedAdRecord


class GoogleNormalizer(INormalizer):
    """Infrastructure implementation of INormalizer for Google Ads data.

    Maps Google Ads CSV or API dictionary records into domain NormalizedAdRecord instances,
    performing date normalization, metric sanitization, and defensive metric calculations.
    """

    DATE_FORMATS: list[str] = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y%m%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%SZ",
    ]

    def normalize(self, raw_records: list[dict[str, object]]) -> list[NormalizedAdRecord]:
        """Normalizes raw dictionary records into canonical NormalizedAdRecord instances.

        Args:
            raw_records: List of raw dictionaries extracted from Google Ads source.

        Returns:
            List of normalized ad record domain models.

        Raises:
            NormalizationError: If date parsing fails or essential data is corrupted.
        """
        normalized_records: list[NormalizedAdRecord] = []

        for idx, record in enumerate(raw_records):
            date_str = self._parse_date(record, idx)
            campaign_name = self._get_string(
                record, ["campaign_name", "Campaign Name", "campaign"], "Unknown Campaign"
            )
            country = self._get_string(
                record, ["country_code", "Country", "Country Code", "country"], "GLOBAL"
            )
            currency = self._get_string(
                record, ["currency_code", "Currency", "Currency Code", "currency"], "USD"
            )

            impressions = self._get_int(
                record, ["impressions", "Impressions", "metrics_impressions"]
            )
            clicks = self._get_int(record, ["clicks", "Clicks", "metrics_clicks"])

            spend = self._extract_spend(record)
            conversions = self._get_float(
                record, ["conversions", "Conversions", "metrics_conversions"]
            )
            conversion_value = self._get_float(
                record,
                [
                    "conversions_value",
                    "Conversion Value",
                    "conversion_value",
                    "metrics_conversions_value",
                ],
            )

            # Defensive derived metric calculations
            ctr = (clicks / impressions) if impressions > 0 else None
            cpc = (spend / clicks) if clicks > 0 else None
            cpm = ((spend / impressions) * 1000.0) if impressions > 0 else None
            cpa = (spend / conversions) if conversions > 0 else None
            roas = (conversion_value / spend) if spend > 0 else None

            # Sanitize float derived metrics against NaN/Inf
            ctr = self._sanitize_float(ctr)
            cpc = self._sanitize_float(cpc)
            cpm = self._sanitize_float(cpm)
            cpa = self._sanitize_float(cpa)
            roas = self._sanitize_float(roas)

            norm_record = NormalizedAdRecord(
                date=date_str,
                platform=Platform.GOOGLE_ADS,
                campaign_name=campaign_name,
                country=country,
                currency=currency,
                spend=spend,
                impressions=impressions,
                clicks=clicks,
                conversions=conversions,
                conversion_value=conversion_value,
                ctr=ctr,
                cpc=cpc,
                cpm=cpm,
                cpa=cpa,
                roas=roas,
            )
            normalized_records.append(norm_record)

        return normalized_records

    def _parse_date(self, record: dict[str, object], row_idx: int) -> str:
        raw_val = self._get_raw_val(record, ["date", "Date", "segments_date", "segments.date"])
        if raw_val is None:
            raise NormalizationError(f"Record at index {row_idx} missing 'date' field.")

        val_str = str(raw_val).strip()
        if not val_str:
            raise NormalizationError(f"Record at index {row_idx} has empty date value.")

        for fmt in self.DATE_FORMATS:
            try:
                dt = datetime.strptime(val_str, fmt)
                return dt.date().isoformat()
            except ValueError:
                continue

        # Fallback to ISO fromformat if available
        try:
            dt = datetime.fromisoformat(val_str)
            return dt.date().isoformat()
        except ValueError as err:
            raise NormalizationError(
                f"Record at index {row_idx} has unparseable date '{val_str}'"
            ) from err

    def _extract_spend(self, record: dict[str, object]) -> float:
        # Check for micros spend first (Google GAQL / API style)
        micros_val = self._get_raw_val(record, ["cost_micros", "metrics_cost_micros"])
        if micros_val is not None:
            parsed_micros = self._to_float(micros_val)
            spend = parsed_micros / 1_000_000.0
        else:
            cost_val = self._get_raw_val(record, ["Cost", "cost", "spend", "Spend"])
            spend = self._to_float(cost_val)

        # Sanitize negative spend (clamp to 0.0)
        return max(0.0, spend)

    def _get_string(
        self, record: dict[str, object], candidate_keys: list[str], default: str
    ) -> str:
        raw = self._get_raw_val(record, candidate_keys)
        if raw is None:
            return default
        s = str(raw).strip()
        return s if s else default

    def _get_int(self, record: dict[str, object], candidate_keys: list[str]) -> int:
        raw = self._get_raw_val(record, candidate_keys)
        f_val = self._to_float(raw)
        return max(0, round(f_val))

    def _get_float(self, record: dict[str, object], candidate_keys: list[str]) -> float:
        raw = self._get_raw_val(record, candidate_keys)
        f_val = self._to_float(raw)
        return max(0.0, f_val)

    def _get_raw_val(self, record: dict[str, object], candidate_keys: list[str]) -> object | None:
        for k in candidate_keys:
            if k in record and record[k] is not None:
                return record[k]
        return None

    def _to_float(self, val: Any) -> float:
        if val is None:
            return 0.0
        if isinstance(val, (int, float)):
            if math.isnan(val) or math.isinf(val):
                return 0.0
            return float(val)
        try:
            cleaned = str(val).replace(",", "").strip()
            res = float(cleaned)
            if math.isnan(res) or math.isinf(res):
                return 0.0
            return res
        except (ValueError, TypeError):
            return 0.0

    def _sanitize_float(self, val: float | None) -> float | None:
        if val is None:
            return None
        if math.isnan(val) or math.isinf(val):
            return None
        return val
