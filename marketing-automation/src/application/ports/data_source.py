from typing import Protocol


class IDataReader(Protocol):
    """Abstract port for reading raw marketing data records from a data source."""

    def read(self, file_path: str) -> list[dict[str, object]]:
        """Reads raw data records from the specified file path."""
        ...
