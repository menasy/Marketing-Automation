import math
import os
from typing import Any

import pandas as pd

from src.application.ports.data_source import IDataReader
from src.domain.exceptions import NormalizationError


class MetaCSVReader(IDataReader):
    """Infrastructure implementation of IDataReader for Meta Ads CSV files.

    Reads raw CSV files using Pandas, validates structure, strips whitespace,
    drops duplicate rows, and converts records to pure Python dictionaries.
    """

    REQUIRED_COLUMN_GROUPS: list[list[str]] = [
        ["date_start", "date", "Date"],
        ["campaign_name", "Campaign Name", "campaign"],
    ]

    def read(self, file_path: str) -> list[dict[str, object]]:
        """Reads raw Meta Ads records from a CSV file.

        Args:
            file_path: Absolute or relative path to the CSV file.

        Returns:
            A list of dictionary records containing raw string/numeric values.

        Raises:
            NormalizationError: If file is missing, empty, corrupt, or lacks required columns.
        """
        if not os.path.exists(file_path):
            raise NormalizationError(f"File not found: '{file_path}'")

        try:
            df = pd.read_csv(file_path, skipinitialspace=True)
        except pd.errors.EmptyDataError as err:
            raise NormalizationError(f"CSV file is empty: '{file_path}'") from err
        except Exception as err:
            raise NormalizationError(f"Failed to parse CSV file '{file_path}': {err}") from err

        if df.empty:
            raise NormalizationError(f"CSV file contains no data rows: '{file_path}'")

        # Strip whitespace from column headers
        df.columns = pd.Index([c.strip() for c in df.columns])

        # Validate presence of required column candidate groups
        column_set = set(df.columns)
        for group in self.REQUIRED_COLUMN_GROUPS:
            if not any(col in column_set for col in group):
                raise NormalizationError(
                    f"CSV file '{file_path}' missing required column from candidate group: {group}"
                )

        # Strip whitespace from string cell values
        for col in df.columns:
            if pd.api.types.is_string_dtype(df[col]) or df[col].dtype == "object":
                df[col] = df[col].astype(str).str.strip()

        # Drop exact duplicate rows
        df = df.drop_duplicates()

        # Convert NaNs to None for clean Python dictionary representation
        records_raw: list[dict[str, Any]] = df.to_dict(orient="records")  # type: ignore[assignment]
        clean_records: list[dict[str, object]] = []

        for record in records_raw:
            clean_record: dict[str, object] = {}
            for k, v in record.items():
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    clean_record[k] = None
                else:
                    clean_record[k] = v
            clean_records.append(clean_record)

        return clean_records
