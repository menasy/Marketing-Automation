"""Type-safe Turkish localization mappings for presentation-layer enum display.

This module provides deterministic str -> str mapping functions that translate
internal domain enum values and agent-produced action labels into professional
Turkish labels suitable for Slack Block Kit cards and Markdown reports.

Domain enums (src/domain/enums/) remain untouched; only the presentation layer
consumes these helpers.
"""


# ---------------------------------------------------------------------------
# Action Label Localization
# ---------------------------------------------------------------------------

_ACTION_LABEL_MAP: dict[str, str] = {
    # Budget actions
    "HOLD_CURRENT_BUDGET": "Mevcut Bütçeyi Koru (24 Saat Gözlem)",
    "HOLD": "Mevcut Bütçeyi Koru (24 Saat Gözlem)",
    "DECREASE_BUDGET": "Kademeli Bütçe Kısıtlaması (%15-%20)",
    "DECREASE": "Kademeli Bütçe Kısıtlaması (%15-%20)",
    "INCREASE_BUDGET": "Kontrollü Bütçe Artırımı",
    "INCREASE": "Kontrollü Bütçe Artırımı",
    "REALLOCATE": "Bütçe Yeniden Dağılımı",
    "PAUSE_CAMPAIGN": "Kampanyayı Geçici Olarak Duraklat",
    # Bid actions
    "CAP_TARGET_CPA": "Hedef CPA / tROAS Teklif Tavanı Belirle",
    "ADJUST_TARGET_CPA_ROAS": "Hedef CPA / tROAS Teklif Tavanı Belirle",
    "SWITCH_TO_MANUAL_CPC": "Manuel TBM Stratejisine Geç",
    "SWITCH_STRATEGY": "Manuel TBM Stratejisine Geç",
    # Creative actions
    "ROTATE_CREATIVES": "Yeni Kreatif Varyasyonları Test Et (A/B Split Test)",
    "ROTATE_FATIGUED_CREATIVES": "Yeni Kreatif Varyasyonları Test Et (A/B Split Test)",
    "REFRESH_FATIGUED_CREATIVES": "Yeni Kreatif Varyasyonları Test Et (A/B Split Test)",
    "RUN_A_B_TEST": "Yeni Kreatif Varyasyonları Test Et (A/B Split Test)",
    "AUDIT_LANDING_PAGE": "Açılış Sayfası Denetimi Yap",
    "PAUSE_FATIGUED_ADS": "Yıpranmış Reklamları Pasife Al",
    # Tracking actions
    "AUDIT_PIXEL_CAPI": "Dönüşüm Takip Kurulumunu (Pixel / CAPI / GTM) Denetle",
    "AUDIT_TRACKING_AND_DATA_QUALITY": "Tracking ve Veri Kalitesi Altyapısını Denetle",
    "VERIFY_GTM_TAGS": "GTM Etiketlerini Doğrula",
    "VERIFY_EVENT_DEDUPLICATION": "Event Tekilleştirme ve Satın Alma Tetikleyicilerini Doğrula",
    # No-op actions
    "NO_CHANGE": "Değişiklik Gerekmiyor",
    "NO_ACTION": "Değişiklik Gerekmiyor",
}

# Prefix patterns for dynamic agent-generated strings (e.g. REDUCE_BUDGET_20_PERCENT)
_ACTION_PREFIX_MAP: list[tuple[str, str]] = [
    ("REDUCE_BUDGET", "Kademeli Bütçe Kısıtlaması (%15-%20)"),
    ("DECREASE_BUDGET", "Kademeli Bütçe Kısıtlaması (%15-%20)"),
    ("INCREASE_BUDGET", "Kontrollü Bütçe Artırımı"),
    ("CAP_TARGET", "Hedef CPA / tROAS Teklif Tavanı Belirle"),
    ("PAUSE_FATIGUED", "Yıpranmış Reklamları Pasife Al"),
    ("ROTATE_FATIGUED", "Yeni Kreatif Varyasyonları Test Et (A/B Split Test)"),
    ("REFRESH_FATIGUED", "Yeni Kreatif Varyasyonları Test Et (A/B Split Test)"),
    ("AUDIT_PIXEL", "Dönüşüm Takip Kurulumunu (Pixel / CAPI / GTM) Denetle"),
    ("AUDIT_TRACKING", "Tracking ve Veri Kalitesi Altyapısını Denetle"),
    ("AUDIT_GOOGLE", "Dönüşüm Takip Kurulumunu (Pixel / CAPI / GTM) Denetle"),
    ("VERIFY_GOOGLE", "Dönüşüm Takip Kurulumunu (Pixel / CAPI / GTM) Denetle"),
    ("VERIFY_EVENT", "Event Tekilleştirme ve Satın Alma Tetikleyicilerini Doğrula"),
    ("VERIFY_GTM", "GTM Etiketlerini Doğrula"),
    ("SWITCH_TO_MANUAL", "Manuel TBM Stratejisine Geç"),
]


def localize_action_label(raw: str) -> str:
    """Translate a raw action label into professional Turkish.

    Performs exact match first, then prefix match for dynamic agent strings.
    Falls back to a humanized version of the raw string if no mapping is found.

    Args:
        raw: Raw action label string from agent output or domain enum value.

    Returns:
        Turkish-localized human-readable action label.
    """
    normalized = raw.strip().upper()

    # Exact match
    result = _ACTION_LABEL_MAP.get(normalized)
    if result is not None:
        return result

    # Prefix match for dynamic agent-generated strings
    for prefix, label in _ACTION_PREFIX_MAP:
        if normalized.startswith(prefix):
            return label

    # Fallback: humanize the raw string
    return raw.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Issue Type Localization
# ---------------------------------------------------------------------------

_ISSUE_TYPE_MAP: dict[str, str] = {
    "DATA_QUALITY": "[VERİ / TRACKING HATASI]",
    "PERFORMANCE": "[GERÇEK PERFORMANS DÜŞÜŞÜ]",
    "MIXED": "[KARMA / BELİRSİZ]",
    # Lowercase variants (domain enum values)
    "data_quality": "[VERİ / TRACKING HATASI]",
    "performance": "[GERÇEK PERFORMANS DÜŞÜŞÜ]",
    "mixed": "[KARMA / BELİRSİZ]",
}


def localize_issue_type(raw: str) -> str:
    """Translate a raw issue type into a Turkish diagnostic badge.

    Args:
        raw: Raw issue type string (e.g. 'DATA_QUALITY', 'PERFORMANCE').

    Returns:
        Turkish diagnostic badge string.
    """
    result = _ISSUE_TYPE_MAP.get(raw.strip())
    if result is not None:
        return result
    return f"[{raw.strip().upper()}]"


# ---------------------------------------------------------------------------
# Severity Localization
# ---------------------------------------------------------------------------

_SEVERITY_MAP: dict[str, str] = {
    "CRITICAL": "🔴 KRİTİK",
    "HIGH": "🟠 YÜKSEK",
    "MEDIUM": "🟡 DİKKAT",
    "WARNING": "🟡 DİKKAT",
    "LOW": "🟢 SAĞLIKLI",
    "INFO": "🟢 SAĞLIKLI",
}


def localize_severity(raw: str) -> str:
    """Translate a raw severity level into a Turkish severity badge with emoji.

    Args:
        raw: Raw severity string (e.g. 'CRITICAL', 'HIGH', 'LOW').

    Returns:
        Turkish severity badge with leading emoji.
    """
    result = _SEVERITY_MAP.get(raw.strip().upper())
    if result is not None:
        return result
    return raw.strip().upper()


# ---------------------------------------------------------------------------
# Metric Name Localization
# ---------------------------------------------------------------------------

_METRIC_NAME_MAP: dict[str, str] = {
    "spend": "Harcama ($)",
    "impressions": "Gösterim",
    "clicks": "Tıklama",
    "conversions": "Dönüşüm",
    "conversion_value": "Dönüşüm Değeri",
    "ctr": "Tıklama Oranı (CTR)",
    "cpc": "Tıklama Başı Maliyet (CPC)",
    "cpm": "Bin Gösterim Maliyeti (CPM)",
    "cpa": "Dönüşüm Başı Maliyet (CPA)",
    "roas": "Reklam Harcaması Getirisi (ROAS)",
}


def localize_metric_name(raw: str) -> str:
    """Translate a raw metric name into a Turkish label.

    Args:
        raw: Raw metric name (e.g. 'spend', 'ctr', 'cpa').

    Returns:
        Turkish metric label string.
    """
    result = _METRIC_NAME_MAP.get(raw.strip().lower())
    if result is not None:
        return result
    return raw.strip().upper()


# ---------------------------------------------------------------------------
# Health Status Localization
# ---------------------------------------------------------------------------

_HEALTH_STATUS_MAP: dict[str, str] = {
    "HEALTHY": "🟢 SAĞLIKLI",
    "DEGRADED": "🟡 DÜŞÜK PERFORMANS",
    "CRITICAL": "🔴 KRİTİK",
}


def localize_health_status(raw: str) -> str:
    """Translate a raw data health status into a Turkish badge with emoji.

    Args:
        raw: Raw health status string (e.g. 'HEALTHY', 'DEGRADED', 'CRITICAL').

    Returns:
        Turkish health status badge with emoji.
    """
    result = _HEALTH_STATUS_MAP.get(raw.strip().upper())
    if result is not None:
        return result
    return f"[{raw.strip().upper()}]"


# ---------------------------------------------------------------------------
# Platform Localization
# ---------------------------------------------------------------------------

_PLATFORM_MAP: dict[str, str] = {
    "google_ads": "Google Ads",
    "meta_ads": "Meta Ads",
    "GOOGLE_ADS": "Google Ads",
    "META_ADS": "Meta Ads",
}


def localize_platform(raw: str) -> str:
    """Translate a raw platform identifier into a display-friendly label.

    Args:
        raw: Raw platform string (e.g. 'google_ads', 'META_ADS').

    Returns:
        Display-friendly platform label.
    """
    result = _PLATFORM_MAP.get(raw.strip())
    if result is not None:
        return result
    return raw.strip().replace("_", " ").title()
