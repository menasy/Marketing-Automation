import math

from src.application.ports.currency_provider import ICurrencyProvider
from src.domain.exceptions import NormalizationError
from src.domain.models.ad_record import NormalizedAdRecord


class StaticCurrencyConverter(ICurrencyProvider):
    """Infrastructure implementation of ICurrencyProvider using deterministic static exchange rates.

    Base rates are normalized against USD. Provides reproducible offline conversion capabilities
    for multi-currency advertising performance datasets.
    """

    DEFAULT_USD_RATES: dict[str, float] = {
        "USD": 1.0,
        "EUR": 1.08,
        "GBP": 1.27,
        "TRY": 0.029,
        "CAD": 0.74,
        "AUD": 0.65,
    }

    def __init__(self, custom_rates: dict[str, float] | None = None) -> None:
        """Initializes converter with default or custom USD-base rates."""
        self._rates: dict[str, float] = (
            {k.upper(): v for k, v in custom_rates.items()}
            if custom_rates is not None
            else dict(self.DEFAULT_USD_RATES)
        )

    def convert(
        self, amount: float, from_currency: str, to_currency: str, record_date: str = ""
    ) -> float:
        """Converts monetary amount from source currency to target currency.

        Args:
            amount: The monetary value to convert.
            from_currency: ISO 4217 code of source currency (e.g. 'EUR').
            to_currency: ISO 4217 code of target currency (e.g. 'USD').
            record_date: ISO 8601 date string for historical rate lookup (unused in static fixture).

        Returns:
            Converted monetary amount.

        Raises:
            NormalizationError: If either source or target currency is unsupported.
        """
        if amount == 0.0 or math.isnan(amount) or math.isinf(amount):
            return 0.0

        src_curr = from_currency.strip().upper()
        tgt_curr = to_currency.strip().upper()

        if src_curr == tgt_curr:
            return amount

        if src_curr not in self._rates:
            raise NormalizationError(f"Unsupported source currency for conversion: '{src_curr}'")
        if tgt_curr not in self._rates:
            raise NormalizationError(f"Unsupported target currency for conversion: '{tgt_curr}'")

        src_rate_usd = self._rates[src_curr]
        tgt_rate_usd = self._rates[tgt_curr]

        # Convert to USD base first, then to target currency
        amount_usd = amount * src_rate_usd
        converted_amount = amount_usd / tgt_rate_usd
        return converted_amount

    def convert_record(
        self, record: NormalizedAdRecord, target_currency: str = "USD"
    ) -> NormalizedAdRecord:
        """Normalizes monetary fields in a NormalizedAdRecord to target currency.

        Args:
            record: Incoming NormalizedAdRecord.
            target_currency: Target currency ISO code (defaults to 'USD').

        Returns:
            A new NormalizedAdRecord with converted spend/conversion_value and
            recalculated derived metrics.
        """
        tgt_curr = target_currency.strip().upper()
        if record.currency.strip().upper() == tgt_curr:
            return record

        converted_spend = self.convert(record.spend, record.currency, tgt_curr, record.date)
        converted_val = self.convert(
            record.conversion_value, record.currency, tgt_curr, record.date
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
            currency=tgt_curr,
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
