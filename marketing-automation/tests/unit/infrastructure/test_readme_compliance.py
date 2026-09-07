"""Unit tests for README.md compliance verification against project guidelines."""

from pathlib import Path


def get_readme_path() -> Path:
    """Resolve the absolute path to project root README.md."""

    current_file = Path(__file__).resolve()
    project_root = current_file.parents[3]
    readme_path = project_root / "README.md"
    return readme_path


def test_readme_exists() -> None:
    """Verify that README.md exists in the project root."""

    readme_path = get_readme_path()
    assert readme_path.exists(), f"README.md not found at {readme_path}"
    assert readme_path.is_file(), f"README.md path {readme_path} is not a file"


def test_readme_contains_all_24_canonical_sections() -> None:
    """Verify that README.md contains all 24 numbered headers verbatim."""

    expected_headers: list[str] = [
        "## 1. Overview",
        "## 2. Architecture",
        "## 3. End-to-End Flow",
        "## 4. Project Structure",
        "## 5. Data Layer",
        "## 6. Normalized Schema",
        "## 7. Metric Definitions",
        "## 8. Anomaly Detection",
        "## 9. Threshold Rationale & False-Positive Guards",
        "## 10. AI Agent Architecture",
        "## 11. Tool Architecture",
        "## 12. Grounding & Validation",
        "## 13. Top 3 Findings",
        "## 14. Automation",
        "## 15. API Integration Note",
        "## 16. Setup",
        "## 17. Running Locally",
        "## 18. Running Tests",
        "## 19. n8n Setup",
        "## 20. Slack Setup",
        "## 21. Technical Decisions",
        "## 22. Scope & Time Constraints (Out of Scope)",
        "## 23. AI Usage",
        "## 24. Limitations",
    ]

    readme_content = get_readme_path().read_text(encoding="utf-8")

    missing_headers: list[str] = []
    for header in expected_headers:
        if header not in readme_content:
            missing_headers.append(header)

    assert not missing_headers, f"README.md is missing mandatory section headers: {missing_headers}"


def test_section_15_api_integration_note_length() -> None:
    """Verify Section 15 (API Integration Note) strictly consists of <= 10 physical lines."""

    readme_content = get_readme_path().read_text(encoding="utf-8")

    start_token = "## 15. API Integration Note"
    end_token = "## 16. Setup"

    assert start_token in readme_content, f"Header '{start_token}' missing from README.md"
    assert end_token in readme_content, f"Header '{end_token}' missing from README.md"

    start_idx = readme_content.find(start_token)
    end_idx = readme_content.find(end_token, start_idx)

    assert end_idx > start_idx, "Section 16 header must appear after Section 15 header"

    section_15_raw = readme_content[start_idx:end_idx].strip()
    section_15_lines = section_15_raw.splitlines()

    line_count = len(section_15_lines)
    assert line_count <= 10, (
        f"Section 15 (API Integration Note) exceeds 10 physical lines: {line_count} lines found.\n"
        f"Content:\n{section_15_raw}"
    )


def test_readme_contains_key_architectural_terms() -> None:
    """Verify presence of key architectural terms in README.md."""

    readme_content = get_readme_path().read_text(encoding="utf-8")

    # 1. Canonical grain
    assert "platform × account × campaign × country × day" in readme_content, (
        "Canonical analytical grain declaration missing"
    )

    # 2. Threshold math
    assert "|Z| >= 2.0" in readme_content or r"|Z| \ge 2.0" in readme_content, (
        "Z-score threshold rationale missing"
    )

    # 3. Guardrails
    assert "DeterministicFallbackGenerator" in readme_content, (
        "DeterministicFallbackGenerator term missing from README.md"
    )
    assert "UnsupportedClaimRule" in readme_content, (
        "UnsupportedClaimRule term missing from README.md"
    )

    # 4. Configured FX rate justification
    expected_fx_quote = (
        "For reproducibility and zero external network dependency in daily analytical pipelines"
    )
    assert expected_fx_quote in readme_content, "FX rate justification quote missing from README.md"
