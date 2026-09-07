"""Unit tests for FastAPI presentation endpoints, CLI command parsing, and DRY dispatching."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from src.application.dto.pipeline_request import PipelineRequest
from src.cli.main import build_parser, main
from src.domain.models.pipeline_result import PipelineResult
from src.presentation.api.app import app
from src.presentation.api.dependencies import get_run_pipeline_use_case

client = TestClient(app)


def create_mock_pipeline_result(status: str = "success") -> PipelineResult:
    """Helper to create a mock domain PipelineResult entity."""
    return PipelineResult(
        execution_id="test-exec-12345",
        status=status,
        anomalies_count=2,
        critical_count=1,
        duration_seconds=1.23,
        briefing_summary="Sabah Özeti: 2 anomali tespit edildi.",
        top_anomalies=["- *Campaign A* (Meta/US): Conversions 100 -> 0"],
        recommended_actions=["Campaign A: REDUCE_BUDGET_20_PERCENT"],
        top_3_findings=[
            {
                "campaign_name": "Campaign A",
                "platform": "meta_ads",
                "country": "US",
                "metric_change": "Conversions: 100 → 0 (-100%)",
                "issue_type": "VERİ / TRACKING HATASI",
                "operational_action": "CAPI eventlerini kontrol edin",
                "severity": "CRITICAL",
                "score": "95.0",
            }
        ],
        output_files={
            "anomalies_json": "output/anomalies.json",
            "operational_assessment_md": "output/operational_assessment.md",
            "top_3_findings_md": "output/top_3_findings.md",
            "sample_briefing_md": "output/sample_briefing.md",
        },
        stage_statuses={
            "normalize_data": "success",
            "build_baseline": "success",
            "detect_anomalies": "success",
            "compile_dossier": "success",
            "agent_reasoning": "success",
            "write_artifacts": "success",
            "dispatch_slack": "success",
        },
    )


class TestFastAPIEndpoints:
    """Unit tests for FastAPI pipeline routes."""

    def test_run_pipeline_success(self) -> None:
        """Verify POST /api/v1/pipeline/run invokes use case and returns HTTP 200."""
        mock_use_case = MagicMock()
        mock_use_case.execute = AsyncMock(
            return_value=create_mock_pipeline_result(status="success")
        )

        app.dependency_overrides[get_run_pipeline_use_case] = lambda: mock_use_case

        try:
            payload = {
                "window_days": 14,
                "reporting_currency": "USD",
                "output_dir": "output",
            }
            response = client.post("/api/v1/pipeline/run", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["execution_id"] == "test-exec-12345"
            assert data["status"] == "success"
            assert data["anomalies_count"] == 2
            assert len(data["top_3_findings"]) == 1
            assert data["top_3_findings"][0]["campaign_name"] == "Campaign A"
            mock_use_case.execute.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    def test_run_pipeline_failed_status_returns_400(self) -> None:
        """Verify POST /api/v1/pipeline/run returns HTTP 400 when status is 'failed'."""
        mock_use_case = MagicMock()
        mock_use_case.execute = AsyncMock(return_value=create_mock_pipeline_result(status="failed"))

        app.dependency_overrides[get_run_pipeline_use_case] = lambda: mock_use_case

        try:
            response = client.post("/api/v1/pipeline/run", json={})
            assert response.status_code == 400
            assert "failed" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()


class TestCLIExecution:
    """Unit tests for Headless CLI argument parsing and dispatching."""

    def test_cli_build_parser_defaults(self) -> None:
        """Verify default argument parsing in CLI parser."""
        parser = build_parser()
        args = parser.parse_args([])
        assert args.window_days == 14
        assert args.currency == "USD"
        assert args.output_dir == "output"
        assert args.target_date is None

    def test_cli_build_parser_custom_args(self) -> None:
        """Verify CLI parser with custom --date, --data-dir, --output-dir, --window-days."""
        parser = build_parser()
        argv = [
            "--date",
            "2026-09-03",
            "--data-dir",
            "custom_data/",
            "--output-dir",
            "custom_out/",
            "--window-days",
            "21",
            "--currency",
            "EUR",
        ]
        args = parser.parse_args(argv)
        assert args.target_date == "2026-09-03"
        assert args.data_dir == "custom_data/"
        assert args.output_dir == "custom_out/"
        assert args.window_days == 21
        assert args.currency == "EUR"

    @patch("src.cli.main.RunPipelineUseCase")
    def test_cli_main_success(self, mock_use_case_cls: MagicMock) -> None:
        """Verify CLI main() dispatches to RunPipelineUseCase and exits 0."""
        mock_instance = MagicMock()
        mock_instance.execute = AsyncMock(return_value=create_mock_pipeline_result("success"))
        mock_use_case_cls.return_value = mock_instance

        argv = [
            "--target-date",
            "2026-09-03",
            "--data-dir",
            "data/",
            "--output-dir",
            "output/",
            "--window-days",
            "14",
        ]

        exit_code = main(argv)
        assert exit_code == 0
        mock_instance.execute.assert_awaited_once()

        # Check argument mapping in request
        request: PipelineRequest = mock_instance.execute.call_args[0][0]
        assert request.target_date == date(2026, 9, 3)
        assert request.data_dir == "data/"
        assert request.output_dir == "output/"
        assert request.window_days == 14

    def test_cli_main_invalid_date(self) -> None:
        """Verify CLI main() returns exit code 1 on invalid date format."""
        exit_code = main(["--target-date", "invalid-date-format"])
        assert exit_code == 1
