"""Integration tests for FastAPI endpoints, dependency injection, and exception handlers."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.domain.exceptions import NormalizationError
from src.presentation.api.app import app
from src.presentation.api.dependencies import get_run_pipeline_use_case

client = TestClient(app)


def test_health_check_endpoint() -> None:
    """Verify GET /health returns 200 OK with expected status JSON."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "environment" in data
    assert "version" in data


def test_pipeline_run_endpoint_success() -> None:
    """Verify POST /api/v1/pipeline/run executes successfully with HTTP 200."""
    response = client.post(
        "/api/v1/pipeline/run",
        json={
            "google_csv_path": "data/google_ads_daily.csv",
            "meta_csv_path": "data/meta_ads_daily.csv",
            "window_days": 14,
            "reporting_currency": "USD",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "execution_id" in data
    assert data["status"] in ("success", "partial_success")
    assert isinstance(data["anomalies_count"], int)
    assert isinstance(data["critical_count"], int)
    assert isinstance(data["duration_seconds"], float)
    assert isinstance(data["output_files"], dict)


def test_pipeline_run_endpoint_invalid_params() -> None:
    """Verify POST /api/v1/pipeline/run with invalid window_days returns HTTP 422."""
    response = client.post(
        "/api/v1/pipeline/run",
        json={"window_days": -5},
    )
    assert response.status_code == 422


def test_pipeline_run_domain_exception_handler() -> None:
    """Verify custom domain exception translates to HTTP 400 Bad Request."""
    mock_use_case = MagicMock()
    mock_use_case.execute.side_effect = NormalizationError("Corrupted CSV input format")

    app.dependency_overrides[get_run_pipeline_use_case] = lambda: mock_use_case

    try:
        response = client.post("/api/v1/pipeline/run", json={})
        assert response.status_code == 400
        data = response.json()
        assert "Corrupted CSV input format" in data["detail"]
        assert data["error_type"] == "NormalizationError"
    finally:
        app.dependency_overrides.clear()


def test_pipeline_run_unhandled_exception_handler() -> None:
    """Verify unhandled infrastructure error translates to HTTP 500 Internal Server Error."""
    mock_use_case = MagicMock()
    mock_use_case.execute.side_effect = RuntimeError("Unexpected I/O failure")

    app.dependency_overrides[get_run_pipeline_use_case] = lambda: mock_use_case

    no_raise_client = TestClient(app, raise_server_exceptions=False)
    try:
        response = no_raise_client.post("/api/v1/pipeline/run", json={})
        assert response.status_code == 500
        data = response.json()
        assert "Internal server error" in data["detail"]
    finally:
        app.dependency_overrides.clear()
