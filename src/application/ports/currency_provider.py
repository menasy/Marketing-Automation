from typing import Protocol


class ICurrencyProvider(Protocol):
    """Abstract port for converting monetary amounts between currencies."""

    def convert(
        self, amount: float, from_currency: str, to_currency: str, record_date: str = ""
    ) -> float:
        """Converts monetary amount from source currency to target currency.

        Args:
            amount: The monetary value to convert.
            from_currency: ISO 4217 code of source currency (e.g. 'EUR', 'GBP').
            to_currency: ISO 4217 code of target currency (e.g. 'USD').
            record_date: ISO 8601 date string for historical exchange rate lookup.

        Returns:
            The converted monetary amount.
        """
        ...
