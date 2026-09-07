"""Unit tests for OperationalReportWriter infrastructure reporter."""

from pathlib import Path

from src.domain.enums.metric_type import MetricType
from src.domain.enums.operational import (
    BidAction,
    BudgetAction,
    CreativeAction,
    IssueType,
    TrackingAction,
)
from src.domain.enums.platform import Platform
from src.domain.enums.severity import Severity
from src.domain.models.operational_finding import OperationalFinding
from src.infrastructure.reporting.operational_report import OperationalReportWriter


def test_operational_report_writer_renders_and_saves_file(tmp_path: Path) -> None:
    """Verify that OperationalReportWriter renders Markdown and writes it to disk."""
    findings = [
        OperationalFinding(
            campaign_name="US_Search_Brand",
            platform=Platform.GOOGLE_ADS,
            country="US",
            primary_metric=MetricType.CONVERSIONS,
            severity=Severity.CRITICAL,
            issue_type=IssueType.DATA_QUALITY,
            evidence_summary="CONVERSIONS changed by -100.0% (current: 0.00, baseline: 50.00)",
            business_impact="Abrupt conversion tracking failure with active spend of $200.00.",
            metric_change="CONVERSIONS: 50.00 → 0.00 (-100%) | SPEND: $200 → $200 (+0%)",
            operational_action="Google Ads CAPI/Pixel entegrasyonunu kontrol edin.",
            budget_action=BudgetAction.HOLD.value,
            bid_action=BidAction.NO_CHANGE.value,
            creative_action=CreativeAction.NO_ACTION.value,
            tracking_action=TrackingAction.AUDIT_PIXEL_CAPI.value,
            score=185.0,
        ),
        OperationalFinding(
            campaign_name="EU_Retargeting_Meta",
            platform=Platform.META_ADS,
            country="DE",
            primary_metric=MetricType.CPA,
            severity=Severity.HIGH,
            issue_type=IssueType.PERFORMANCE,
            evidence_summary="CPA changed by +160.0% (current: 65.00, baseline: 25.00)",
            business_impact="Performance decline: CPA increased by 160.0%.",
            metric_change="CPA: $25 → $65 (+160%)",
            operational_action="Günlük bütçeyi %20 kısın, yıpranmış kreatifleri yenileyin.",
            budget_action=BudgetAction.DECREASE.value,
            bid_action=BidAction.ADJUST_TARGET_CPA_ROAS.value,
            creative_action=CreativeAction.REFRESH_FATIGUED_CREATIVES.value,
            tracking_action=TrackingAction.NO_ACTION.value,
            score=142.5,
        ),
    ]

    writer = OperationalReportWriter()
    target_file = tmp_path / "top_3_findings.md"

    rendered_text = writer.render_and_save(findings, str(target_file))

    assert target_file.is_file()
    saved_content = target_file.read_text(encoding="utf-8")
    assert saved_content == rendered_text

    # Section layout checks — Turkish headers
    assert "# Operasyonel Yönetici Raporu: En Kritik 3 Bulgu" in saved_content
    assert "Özet Matrisi" in saved_content
    assert "US_Search_Brand" in saved_content
    assert "EU_Retargeting_Meta" in saved_content

    # Case Study explicit questions checks
    q1 = (
        "Soru 1: Bulgu gerçek bir performans sorununa mı işaret etmektedir, "
        "yoksa verinin kendisinden mi kaynaklanmaktadır?"
    )
    q2 = "Soru 2: Bütçe, teklif veya kreatif tarafında hangi aksiyonu alırdınız?"

    assert q1 in saved_content
    assert q2 in saved_content

    # Turkish localized action labels — no raw enum leakage
    assert "Mevcut Bütçeyi Koru" in saved_content
    assert "Kademeli Bütçe Kısıtlaması" in saved_content
    assert "Dönüşüm Takip Kurulumunu" in saved_content
    assert "Değişiklik Gerekmiyor" in saved_content

    # Turkish issue badges
    assert "[VERİ / TRACKING HATASI]" in saved_content
    assert "[GERÇEK PERFORMANS DÜŞÜŞÜ]" in saved_content

    # Turkish severity labels
    assert "🔴 KRİTİK" in saved_content
    assert "🟠 YÜKSEK" in saved_content

    # Word count length constraint check (Max 1200 words)
    words = saved_content.split()
    assert len(words) <= 1200, f"Report word count ({len(words)}) exceeds 1200 word limit"


def test_operational_report_writer_empty_findings(tmp_path: Path) -> None:
    """Verify report writer output when findings list is empty."""
    writer = OperationalReportWriter()
    target_file = tmp_path / "empty_findings.md"

    rendered = writer.render_and_save([], str(target_file))

    assert target_file.is_file()
    assert "kritik operasyonel anomali" in rendered
