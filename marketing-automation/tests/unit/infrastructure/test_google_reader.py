from pathlib import Path

import pytest

from src.domain.exceptions import NormalizationError
from src.infrastructure.data.csv.google_ads_reader import GoogleCSVReader


def test_read_real_google_ads_daily_csv() -> None:
    reader = GoogleCSVReader()
    real_csv_path = "data/google_ads_daily.csv"
    assert Path(real_csv_path).exists(), "Sample CSV data/google_ads_daily.csv must exist"

    records = reader.read(real_csv_path)
    assert isinstance(records, list)
    assert len(records) > 0

    first_record = records[0]
    assert "date" in first_record
    assert "campaign_name" in first_record
    assert "impressions" in first_record
    assert "clicks" in first_record
    assert "cost_micros" in first_record


def test_read_synthetic_valid_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "valid_google.csv"
    csv_content = (
        " date , campaign_name , country_code , impressions , clicks , cost_micros \n"
        " 2026-07-06 ,  NK | Search | Brand  , DE , 1000 , 50 , 100000000 \n"
        " 2026-07-07 ,  NK | Search | Brand  , DE , 1200 , 60 , 120000000 \n"
    )
    csv_file.write_text(csv_content, encoding="utf-8")

    reader = GoogleCSVReader()
    records = reader.read(str(csv_file))

    assert len(records) == 2
    assert records[0]["date"] == "2026-07-06"
    assert records[0]["campaign_name"] == "NK | Search | Brand"
    assert records[0]["country_code"] == "DE"
    assert records[0]["impressions"] == 1000
    assert records[0]["clicks"] == 50
    assert records[0]["cost_micros"] == 100000000


def test_read_missing_file() -> None:
    reader = GoogleCSVReader()
    with pytest.raises(NormalizationError, match="File not found"):
        reader.read("non_existent_file_path.csv")


def test_read_empty_file(tmp_path: Path) -> None:
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("", encoding="utf-8")

    reader = GoogleCSVReader()
    with pytest.raises(NormalizationError, match="CSV file is empty"):
        reader.read(str(csv_file))


def test_read_missing_required_columns(tmp_path: Path) -> None:
    csv_file = tmp_path / "missing_cols.csv"
    csv_content = "date,impressions,clicks\n2026-07-06,100,10\n"
    csv_file.write_text(csv_content, encoding="utf-8")

    reader = GoogleCSVReader()
    with pytest.raises(NormalizationError, match="missing required column"):
        reader.read(str(csv_file))


def test_read_duplicate_rows(tmp_path: Path) -> None:
    csv_file = tmp_path / "duplicates.csv"
    csv_content = (
        "date,campaign_name,impressions,clicks,cost_micros\n"
        "2026-07-06,Campaign A,100,10,1000000\n"
        "2026-07-06,Campaign A,100,10,1000000\n"
    )
    csv_file.write_text(csv_content, encoding="utf-8")

    reader = GoogleCSVReader()
    records = reader.read(str(csv_file))
    assert len(records) == 1
