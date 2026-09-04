from fastapi.testclient import TestClient

from src.presentation.api.app import app

client = TestClient(app)


def test_health_endpoint() -> None:
    """Verify that GET /health returns 200 OK and expected status JSON structure."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "environment" in data
    assert data["version"] == "0.1.0"
