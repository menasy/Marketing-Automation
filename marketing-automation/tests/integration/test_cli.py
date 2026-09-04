"""Integration tests for Headless CLI entrypoint."""

import json
import subprocess
import sys
from pathlib import Path

from src.cli.main import main


def test_cli_main_direct_execution() -> None:
    """Verify executing main() directly with real sample datasets."""
    google_csv = "data/google_ads_daily.csv"
    meta_csv = "data/meta_ads_daily.csv"

    assert Path(google_csv).exists(), f"{google_csv} must exist for integration testing"
    assert Path(meta_csv).exists(), f"{meta_csv} must exist for integration testing"

    exit_code = main(
        [
            "--google-csv",
            google_csv,
            "--meta-csv",
            meta_csv,
            "--window-days",
            "14",
            "--currency",
            "USD",
        ]
    )

    assert exit_code == 0
    assert Path("output/anomalies.json").exists()
    assert Path("output/top_3_findings.md").exists()

    content = Path("output/anomalies.json").read_text(encoding="utf-8")
    parsed = json.loads(content)
    assert isinstance(parsed, list)


def test_cli_invalid_target_date_format(capsys: object) -> None:
    """Verify that an invalid --target-date yields exit code 1 and prints an error message."""
    exit_code = main(["--target-date", "invalid-date-format"])
    assert exit_code == 1


def test_cli_subprocess_invocation() -> None:
    """Verify invoking the CLI as a module python -m src.cli.main."""
    google_csv = "data/google_ads_daily.csv"
    meta_csv = "data/meta_ads_daily.csv"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.cli.main",
            "--google-csv",
            google_csv,
            "--meta-csv",
            meta_csv,
            "--window-days",
            "14",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "MARKETING AUTOMATION PIPELINE SUMMARY" in result.stdout
    assert "Execution ID" in result.stdout
    assert "Status" in result.stdout


def test_cli_help_flag() -> None:
    """Verify CLI --help flag output."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Marketing Automation Anomaly Detection Pipeline CLI" in result.stdout
    assert "--google-csv" in result.stdout
    assert "--meta-csv" in result.stdout
