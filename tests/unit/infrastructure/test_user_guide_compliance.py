"""Unit tests for USER.md compliance verification against operations runbook requirements."""

from pathlib import Path


def get_user_md_path() -> Path:
    """Resolve absolute path to workspace USER.md file."""

    current_file = Path(__file__).resolve()
    project_root = current_file.parents[3]
    user_md_path = project_root / "USER.md"
    return user_md_path


def test_user_md_exists() -> None:
    """Verify that USER.md exists in the project root."""

    user_md_path = get_user_md_path()
    assert user_md_path.exists(), f"USER.md not found at {user_md_path}"
    assert user_md_path.is_file(), f"USER.md path {user_md_path} is not a file"


def test_user_md_contains_all_operational_sections() -> None:
    """Verify that USER.md contains all 6 mandatory operational section headers."""

    expected_headers: list[str] = [
        "Bölüm 1: Hızlı Başlangıç & Günlük 08:00 Operasyon Rutini",
        "Bölüm 2: Çıktı Dosyaları ve Kullanım Amaçları",
        "Bölüm 3: Vaka İnceleme Teşhis Rehberi — Soru 1",
        "Bölüm 4: Vaka Aksiyon Rehberi — Soru 2",
        "Bölüm 5: Slack Bildirimleri, Sağlık Rozetleri ve Müdahale SLA'ları",
        "Bölüm 6: Sorun Giderme, Fallback Modu Tespiti ve Manuel Tetikleme",
    ]

    user_content = get_user_md_path().read_text(encoding="utf-8")

    missing_headers: list[str] = []
    for header in expected_headers:
        if header not in user_content:
            missing_headers.append(header)

    assert not missing_headers, (
        f"USER.md is missing mandatory operational headers: {missing_headers}"
    )


def test_user_md_contains_required_operational_tokens() -> None:
    """Verify presence of core operational diagnostic tokens, categories, and SLAs."""

    user_content = get_user_md_path().read_text(encoding="utf-8")

    # 1. Case Study Questions
    assert "Soru 1" in user_content, "Token 'Soru 1' missing from USER.md"
    assert "Soru 2" in user_content, "Token 'Soru 2' missing from USER.md"

    # 2. Diagnostic Categories
    assert "[VERİ / TRACKING HATASI]" in user_content, (
        "Diagnostic class '[VERİ / TRACKING HATASI]' missing from USER.md"
    )
    assert "[GERÇEK PERFORMANS DÜŞÜŞÜ]" in user_content, (
        "Diagnostic class '[GERÇEK PERFORMANS DÜŞÜŞÜ]' missing from USER.md"
    )

    # 3. Fallback Mode Identifier
    assert "[DETERMINISTIC FALLBACK - AGENT UNASSISTED]" in user_content, (
        "Fallback identifier '[DETERMINISTIC FALLBACK - AGENT UNASSISTED]' missing from USER.md"
    )

    # 4. Slack Health Badges
    assert "HEALTHY" in user_content, "Health badge 'HEALTHY' missing from USER.md"
    assert "DEGRADED" in user_content, "Health badge 'DEGRADED' missing from USER.md"
    assert "CRITICAL" in user_content, "Health badge 'CRITICAL' missing from USER.md"

    # 5. SLA Thresholds
    assert "24 Saat" in user_content, "SLA threshold '24 Saat' missing from USER.md"
    assert "4 Saat" in user_content, "SLA threshold '4 Saat' missing from USER.md"
    assert "30 Dakika" in user_content, "SLA threshold '30 Dakika' missing from USER.md"
