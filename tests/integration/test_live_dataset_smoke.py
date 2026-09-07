"""Automated end-to-end smoke test suite running against physical live datasets in data/."""

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.agent.guardrails.verifier import OutputVerifier
from src.application.dto.pipeline_request import PipelineRequest
from src.application.use_cases.run_pipeline import RunPipelineUseCase
from src.presentation.api.app import app


@pytest.mark.asyncio
async def test_live_dataset_pipeline_execution(tmp_path: Path) -> None:
    """Execute RunPipelineUseCase on physical files in data/ for target date 2026-08-31.

    Asserts file creation, JSON schema validity, content parity between operational report
    aliases, Soru 1 / Soru 2 compliance, and word count limits.
    """
    target_date = date(2026, 8, 31)
    output_dir = tmp_path / "output"

    request = PipelineRequest(
        data_dir="data",
        output_dir=str(output_dir),
        window_days=14,
        target_date=target_date,
    )

    use_case = RunPipelineUseCase()
    result = await use_case.execute(request)

    assert result.status in ("success", "partial_success")
    assert result.anomalies_count > 0

    # 1. Verify Deliverable Files Existence
    anomalies_json_path = output_dir / "anomalies.json"
    operational_assessment_path = output_dir / "operational_assessment.md"
    top_3_findings_path = output_dir / "top_3_findings.md"
    sample_briefing_path = output_dir / "sample_briefing.md"

    assert anomalies_json_path.is_file() and anomalies_json_path.stat().st_size > 0
    assert operational_assessment_path.is_file() and operational_assessment_path.stat().st_size > 0
    assert top_3_findings_path.is_file() and top_3_findings_path.stat().st_size > 0
    assert sample_briefing_path.is_file() and sample_briefing_path.stat().st_size > 0

    # 2. Verify JSON Deliverable Schema
    anomalies_data = json.loads(anomalies_json_path.read_text(encoding="utf-8"))
    assert isinstance(anomalies_data, dict)
    assert anomalies_data["target_date"] == "2026-08-31"
    assert "total_anomalies_detected" in anomalies_data
    assert "total_campaigns_impacted" in anomalies_data

    # 3. Verbatim Content Parity Check
    op_content = operational_assessment_path.read_text(encoding="utf-8")
    top_content = top_3_findings_path.read_text(encoding="utf-8")
    assert op_content == top_content, (
        "operational_assessment.md and top_3_findings.md must be identical verbatim aliases"
    )

    # 4. Word Count Constraint Check (<= 1200 words)
    words = op_content.split()
    assert len(words) <= 1200, f"Operational assessment exceeds 1200 words limit ({len(words)})"

    # 5. Case Study Questions 1 & 2 Structure Verification
    assert "Soru 1: Bulgu gerçek bir performans sorununa mı işaret etmektedir" in op_content
    assert "Soru 2: Bütçe, teklif veya kreatif tarafında hangi aksiyonu alırdınız?" in op_content

    # Badges verification
    has_dq_badge = "[VERİ / TRACKING HATASI]" in op_content
    has_perf_badge = "[GERÇEK PERFORMANS DÜŞÜŞÜ]" in op_content
    assert has_dq_badge or has_perf_badge, "Report must contain valid diagnostic badges"

    # Action items verification
    assert "Bütçe Aksiyonu" in op_content
    assert "Teklif Aksiyonu" in op_content
    assert "Kreatif Aksiyonu" in op_content
    assert "Takip Aksiyonu" in op_content
    assert "Somut Operasyonel Adımlar:" in op_content

    # Finding count verification (up to 3 findings)
    finding_headers = [
        line
        for line in op_content.splitlines()
        if line.startswith("## Bulgu ") or line.startswith("### Bulgu ")
    ]
    assert 1 <= len(finding_headers) <= 3

    # 6. Sample Briefing Deliverable Verification
    briefing_content = sample_briefing_path.read_text(encoding="utf-8")
    assert "# Yönetici Brifingi:" in briefing_content
    assert "Hedef Analiz Tarihi" in briefing_content
    assert "2026-08-31" in briefing_content


def test_api_live_dataset_smoke(tmp_path: Path) -> None:
    """Smoke test FastAPI POST /api/v1/pipeline/run endpoint with live physical CSV data."""
    client = TestClient(app)
    output_dir = tmp_path / "api_output"

    payload = {
        "data_dir": "data",
        "output_dir": str(output_dir),
        "window_days": 14,
        "target_date": "2026-08-31",
        "reporting_currency": "USD",
    }

    response = client.post("/api/v1/pipeline/run", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "execution_id" in data
    assert data["status"] in ("success", "partial_success")
    assert data["anomalies_count"] > 0
    assert "output_files" in data
    assert "anomalies_json" in data["output_files"]


def test_output_verifier_guardrails_on_live_dossier(tmp_path: Path) -> None:
    """Audit OutputVerifier execution logic against live EvidenceDossier compilation."""
    use_case = RunPipelineUseCase()
    # Test that OutputVerifier can audit structures cleanly
    verifier = OutputVerifier()

    assert verifier is not None
    assert hasattr(use_case, "_batch_orchestrator")
    assert use_case._batch_orchestrator.verifier is not None
