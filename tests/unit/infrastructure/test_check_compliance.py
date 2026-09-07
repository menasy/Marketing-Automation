"""Unit tests for CHECK.md compliance verification against case specifications."""

from pathlib import Path


def get_check_path() -> Path:
    """Resolve the absolute path to project root CHECK.md."""
    current_file = Path(__file__).resolve()
    project_root = current_file.parents[3]
    check_path = project_root / "CHECK.md"
    return check_path


def test_check_md_exists() -> None:
    """Verify that CHECK.md exists in the project root."""
    check_path = get_check_path()
    assert check_path.exists(), f"CHECK.md not found at {check_path}"
    assert check_path.is_file(), f"CHECK.md path {check_path} is not a file"


def test_check_md_contains_all_sections_and_weights() -> None:
    """Verify that CHECK.md contains all mandatory sections and weighting terms."""
    check_content = get_check_path().read_text(encoding="utf-8")

    mandatory_terms: list[str] = [
        "# E-Trink Global Vaka Değerlendirme & Teslim Denetim Matrisi (CHECK.md)",
        "## 1. Vaka Puanlama Ağırlıkları Özeti",
        "## 2. Madde Madde Vaka Şartnamesi Doğrulama Tablosu",
        "### 2.1. VERİ KATMANI (%30)",
        "### 2.2. ANOMALİ KATMANI",
        "### 2.3. LLM KATMANI (%20)",
        "### 2.4. OTOMASYON KATMANI (%15)",
        "### 2.5. REKLAM OPERASYONU DEĞERLENDİRMESİ (%30 - EN YÜKSEK AĞIRLIK)",
        "### 2.6. TESLİM FORMATI VE GENEL KURALLAR",
        "## 3. Otomatik Test ve Doğrulama Özeti",
        "## 4. Tamamlanma Kriteri (Definition of Done - DoD) Kontrol Listesi",
        "GrainAggregator",
        "GoogleNormalizer",
        "MetaNormalizer",
        "NumericVerifier",
        "UnsupportedClaimRule",
        "DeterministicFallbackGenerator",
        "workflow.json",
        "entrypoint-n8n.sh",
        "operational_assessment.md",
    ]

    missing_terms: list[str] = []
    for term in mandatory_terms:
        if term not in check_content:
            missing_terms.append(term)

    assert not missing_terms, f"CHECK.md is missing mandatory terms or sections: {missing_terms}"
