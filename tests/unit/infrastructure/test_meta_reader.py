from pathlib import Path

import pytest

from src.domain.exceptions import NormalizationError
from src.infrastructure.data.csv.meta_ads_reader import MetaCSVReader


def test_read_real_meta_ads_daily_csv() -> None:
    reader = MetaCSVReader()
    real_csv_path = "data/meta_ads_daily.csv"
    assert Path(real_csv_path).exists(), "Sample CSV data/meta_ads_daily.csv must exist"

    records = reader.read(real_csv_path)
    assert isinstance(records, list)
    assert len(records) > 0

    first_record = records[0]
    assert "date_start" in first_record
    assert "campaign_name" in first_record
    assert "impressions" in first_record
    assert "inline_link_clicks" in first_record
    assert "spend" in first_record


def test_read_synthetic_valid_meta_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "valid_meta.csv"
    csv_content = (
        " date_start , campaign_name , country , impressions , inline_link_clicks , spend \n"
        " 2026-07-06 ,  NK | ABO | Prospecting EU  , DE , 50000 , 600 , 227.61 \n"
        " 2026-07-07 ,  NK | ABO | Prospecting EU  , DE , 46000 , 430 , 142.77 \n"
    )
    csv_file.write_text(csv_content, encoding="utf-8")

    reader = MetaCSVReader()
    records = reader.read(str(csv_file))

    assert len(records) == 2
    assert records[0]["date_start"] == "2026-07-06"
    assert records[0]["campaign_name"] == "NK | ABO | Prospecting EU"
    assert records[0]["country"] == "DE"
    assert records[0]["impressions"] == 50000
    assert records[0]["inline_link_clicks"] == 600
    assert records[0]["spend"] == 227.61


def test_read_missing_file() -> None:
    reader = MetaCSVReader()
    with pytest.raises(NormalizationError, match="File not found"):
        reader.read("non_existent_meta_file.csv")


def test_read_empty_file(tmp_path: Path) -> None:
    csv_file = tmp_path / "empty_meta.csv"
    csv_file.write_text("", encoding="utf-8")

    reader = MetaCSVReader()
    with pytest.raises(NormalizationError, match="CSV file is empty"):
        reader.read(str(csv_file))


def test_read_missing_required_columns(tmp_path: Path) -> None:
    csv_file = tmp_path / "missing_cols_meta.csv"
    csv_content = "date_start,impressions,spend\n2026-07-06,100,10.0\n"
    csv_file.write_text(csv_content, encoding="utf-8")

    reader = MetaCSVReader()
    with pytest.raises(NormalizationError, match="missing required column"):
        reader.read(str(csv_file))


def test_read_duplicate_rows(tmp_path: Path) -> None:
    csv_file = tmp_path / "duplicates_meta.csv"
    csv_content = (
        "date_start,campaign_name,impressions,inline_link_clicks,spend\n"
        "2026-07-06,Campaign Meta,100,10,25.0\n"
        "2026-07-06,Campaign Meta,100,10,25.0\n"
    )
    csv_file.write_text(csv_content, encoding="utf-8")

    reader = MetaCSVReader()
    records = reader.read(str(csv_file))
    assert len(records) == 1
