"""Comprehensive End-to-End (E2E) integration test for dual-mode execution (CLI and API)."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.cli.main import main as cli_main
from src.presentation.api.app import app


def test_dual_mode_end_to_end_pipeline_parity() -> None:
    """Execute pipeline via both CLI and API against real dataset to assert parity."""
    google_csv = "data/google_ads_daily.csv"
    meta_csv = "data/meta_ads_daily.csv"

    assert Path(google_csv).exists(), f"Sample dataset {google_csv} must exist for E2E test"
    assert Path(meta_csv).exists(), f"Sample dataset {meta_csv} must exist for E2E test"

    # 1. Execute pipeline via Headless CLI
    cli_exit_code = cli_main(
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
    assert cli_exit_code == 0

    cli_anomalies_file = Path("output/anomalies.json")
    cli_assessment_file = Path("output/operational_assessment.md")
    cli_findings_file = Path("output/top_3_findings.md")
    cli_briefing_file = Path("output/sample_briefing.md")

    assert cli_anomalies_file.exists()
    assert cli_assessment_file.exists()
    assert cli_findings_file.exists()
    assert cli_briefing_file.exists()

    assert cli_assessment_file.read_text(encoding="utf-8") == cli_findings_file.read_text(
        encoding="utf-8"
    )

    cli_anomalies = json.loads(cli_anomalies_file.read_text(encoding="utf-8"))
    cli_findings_content = cli_findings_file.read_text(encoding="utf-8")
    cli_briefing_content = cli_briefing_file.read_text(encoding="utf-8")

    assert isinstance(cli_anomalies, (list, dict))
    assert len(cli_findings_content) > 0
    assert len(cli_briefing_content) > 0

    # 2. Execute pipeline via FastAPI REST API
    client = TestClient(app)
    api_response = client.post(
        "/api/v1/pipeline/run",
        json={
            "google_csv_path": google_csv,
            "meta_csv_path": meta_csv,
            "window_days": 14,
            "reporting_currency": "USD",
        },
    )

    assert api_response.status_code == 200
    api_data = api_response.json()
    assert api_data["status"] in ("success", "partial_success")

    api_anomalies_file = Path(api_data["output_files"]["anomalies_json"])
    assert api_anomalies_file.exists()

    api_anomalies = json.loads(api_anomalies_file.read_text(encoding="utf-8"))
    assert api_anomalies is not None

    # 3. Assert dual-mode business parity
    cli_cnt = (
        cli_anomalies.get("total_anomalies_detected", len(cli_anomalies))
        if isinstance(cli_anomalies, dict)
        else len(cli_anomalies)
    )
    assert cli_cnt == api_data["anomalies_count"]
    assert (
        api_data["output_files"]["operational_assessment_md"] == "output/operational_assessment.md"
    )
    assert api_data["output_files"]["top_3_findings_md"] == "output/top_3_findings.md"
    assert api_data["output_files"]["sample_briefing_md"] == "output/sample_briefing.md"
