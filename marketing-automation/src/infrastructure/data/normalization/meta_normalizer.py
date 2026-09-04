import json
import math
from datetime import datetime
from typing import Any

from src.application.ports.normalizer import INormalizer
from src.domain.enums.platform import Platform
from src.domain.exceptions import NormalizationError
from src.domain.models.ad_record import NormalizedAdRecord


class MetaNormalizer(INormalizer):
    """Infrastructure implementation of INormalizer for Meta Ads data.

    Maps Meta Ads CSV or Marketing API dictionary records into canonical
    NormalizedAdRecord domain model instances. Handles Meta-specific schema
    variations, structured action/action_values arrays, and date parsing.
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

    TARGET_ACTION_TYPES: list[str] = [
        "purchase",
        "offsite_conversion.fb_pixel_purchase",
        "offsite_conversion",
        "lead",
        "conversion",
    ]

    def normalize(self, raw_records: list[dict[str, object]]) -> list[NormalizedAdRecord]:
        """Normalizes raw dictionary records into canonical NormalizedAdRecord instances.

        Args:
            raw_records: List of raw dictionaries extracted from Meta Ads source.

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
            country = self._get_string(record, ["country", "country_code", "Country"], "GLOBAL")
            currency = self._get_string(record, ["currency", "currency_code", "Currency"], "USD")

            impressions = self._get_int(record, ["impressions", "Impressions"])
            clicks = self._get_int(
                record, ["inline_link_clicks", "link_clicks", "clicks", "Clicks"]
            )

            spend = self._extract_spend(record)
            conversions = self._extract_conversions(record)
            conversion_value = self._extract_conversion_value(record)

            # Derived metrics calculations
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
                platform=Platform.META_ADS,
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
        raw_val = self._get_raw_val(record, ["date_start", "date", "Date", "date_stop", "date_day"])
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

        try:
            dt = datetime.fromisoformat(val_str)
            return dt.date().isoformat()
        except ValueError as err:
            raise NormalizationError(
                f"Record at index {row_idx} has unparseable date '{val_str}'"
            ) from err

    def _extract_spend(self, record: dict[str, object]) -> float:
        cost_val = self._get_raw_val(record, ["spend", "amount_spent", "Cost", "cost"])
        spend = self._to_float(cost_val)
        return max(0.0, spend)

    def _extract_conversions(self, record: dict[str, object]) -> float:
        direct_keys = [
            "actions_purchase",
            "purchases",
            "conversions",
            "actions:offsite_conversion",
            "actions_offsite_conversion",
            "offsite_conversions",
        ]
        raw_direct = self._get_raw_val(record, direct_keys)
        if raw_direct is not None:
            return self._get_float(record, direct_keys)

        raw_actions = record.get("actions")
        if raw_actions is not None:
            return self._extract_from_action_structure(raw_actions)

        return 0.0

    def _extract_conversion_value(self, record: dict[str, object]) -> float:
        direct_keys = [
            "action_values_purchase",
            "purchase_value",
            "conversion_value",
            "action_values:offsite_conversion",
            "action_values_offsite_conversion",
            "value",
        ]
        raw_direct = self._get_raw_val(record, direct_keys)
        if raw_direct is not None:
            return self._get_float(record, direct_keys)

        raw_values = record.get("action_values")
        if raw_values is not None:
            return self._extract_from_action_structure(raw_values)

        return 0.0

    def _extract_from_action_structure(self, action_data: object) -> float:
        parsed_data = action_data
        if isinstance(action_data, str):
            try:
                parsed_data = json.loads(action_data)
            except (json.JSONDecodeError, TypeError):
                return 0.0

        if isinstance(parsed_data, list):
            for item in parsed_data:
                if isinstance(item, dict):
                    item_type = str(item.get("action_type", "")).lower()
                    if any(target in item_type for target in self.TARGET_ACTION_TYPES):
                        return self._to_float(item.get("value"))
        elif isinstance(parsed_data, dict):
            for k, v in parsed_data.items():
                if any(target in str(k).lower() for target in self.TARGET_ACTION_TYPES):
                    return self._to_float(v)

        return 0.0

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
