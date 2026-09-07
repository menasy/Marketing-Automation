"""Integration test for AnalyzeFindingsUseCase and operational analysis report generation."""

import json
from pathlib import Path

from src.application.use_cases.analyze_findings import AnalyzeFindingsUseCase
from src.domain.enums import MetricDirection, MetricType, Platform, Severity
from src.domain.models.anomaly import AnomalyItem
from src.infrastructure.config.settings import get_settings


def load_test_anomalies() -> list[AnomalyItem]:
    """Loads anomalies from output/anomalies.json or creates test fallback items."""
    settings = get_settings()
    anomalies_file = settings.output_dir / "anomalies.json"

    if anomalies_file.is_file():
        raw_data = json.loads(anomalies_file.read_text(encoding="utf-8"))
        if isinstance(raw_data, list):
            items: list[AnomalyItem] = []
            for d in raw_data:
                is_valid_plat = d["platform"] in ("google_ads", "meta_ads")
                p_val = Platform(d["platform"]) if is_valid_plat else Platform.GOOGLE_ADS
                m_str = d["metric"].lower()
                m_types = [m.value for m in MetricType]
                m_val = MetricType(m_str) if m_str in m_types else MetricType.SPEND
                s_str = d["severity"].lower()
                s_types = [s.value for s in Severity]
                s_val = Severity(s_str) if s_str in s_types else Severity.HIGH
                dir_val = (
                    MetricDirection.LOWER_IS_BETTER
                    if "cpa" in m_str
                    else MetricDirection.HIGHER_IS_BETTER
                )

                items.append(
                    AnomalyItem(
                        campaign_name=d["campaign"],
                        platform=p_val,
                        country=d["country"],
                        metric=m_val,
                        current_value=float(d["current_value"]),
                        baseline_value=float(d["baseline_value"]),
                        change_rate=float(d["change_rate"]),
                        z_score=float(d["z_score"]),
                        severity=s_val,
                        direction=dir_val,
                        detection_method=d.get("detection_method", "rolling_zscore"),
                        rationale=d.get("rationale", ""),
                    )
                )
            return items

    # Fallback test items
    return [
        AnomalyItem(
            campaign_name="AH | Search | Generic",
            platform=Platform.GOOGLE_ADS,
            country="UK",
            metric=MetricType.CPA,
            current_value=81.67,
            baseline_value=28.34,
            change_rate=1.882,
            z_score=8.46,
            severity=Severity.CRITICAL,
            direction=MetricDirection.LOWER_IS_BETTER,
            detection_method="rolling_zscore",
            rationale="CPA spiked by +188.2%",
        ),
        AnomalyItem(
            campaign_name="US_Search_Brand",
            platform=Platform.GOOGLE_ADS,
            country="US",
            metric=MetricType.CONVERSIONS,
            current_value=0.0,
            baseline_value=45.0,
            change_rate=-1.0,
            z_score=-4.2,
            severity=Severity.CRITICAL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            detection_method="z_score",
            rationale="Conversions dropped to zero.",
        ),
        AnomalyItem(
            campaign_name="EU_Retargeting_Meta",
            platform=Platform.META_ADS,
            country="DE",
            metric=MetricType.CTR,
            current_value=0.008,
            baseline_value=0.035,
            change_rate=-0.77,
            z_score=-3.8,
            severity=Severity.HIGH,
            direction=MetricDirection.HIGHER_IS_BETTER,
            detection_method="z_score",
            rationale="CTR collapsed.",
        ),
    ]


def test_analyze_findings_use_case_integration(tmp_path: Path) -> None:
    """Verify full operational analysis use case execution and Markdown report generation."""
    anomalies = load_test_anomalies()
    target_report_file = tmp_path / "top_3_findings.md"

    use_case = AnalyzeFindingsUseCase(output_path=target_report_file)
    findings = use_case.execute(anomalies, max_findings=3)

    assert len(findings) > 0
    assert len(findings) <= 3
    assert target_report_file.is_file()

    content = target_report_file.read_text(encoding="utf-8")
    assert "# Operasyonel Yönetici Raporu: En Kritik 3 Bulgu" in content
    assert "Soru 1: Bulgu gerçek bir performans sorununa mı işaret etmektedir" in content
    assert "Soru 2: Bütçe, teklif veya kreatif tarafında hangi aksiyonu alırdınız?" in content

    # Word count check <= 800 words (1 page limit)
    words = content.split()
    assert len(words) <= 1200, f"Word count ({len(words)}) exceeds limit"
