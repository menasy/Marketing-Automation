import logging

import google.generativeai as genai

from src.application.ports.llm_service import ILLMService
from src.domain.models.anomaly import AnomalyItem
from src.domain.models.briefing import ExecutiveBriefing
from src.infrastructure.config.settings import get_settings
from src.infrastructure.llm.output_validator import OutputValidator
from src.infrastructure.llm.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


class GeminiService(ILLMService):
    """Google Gemini LLM Service implementation enforcing strict grounding rules."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        prompt_loader: PromptLoader | None = None,
        validator: OutputValidator | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.gemini_api_key
        self._model_name = model_name or settings.gemini_model or "gemini-3.5-flash"
        self._prompt_loader = prompt_loader or PromptLoader()
        self._validator = validator or OutputValidator()

        if self._api_key:
            genai.configure(api_key=self._api_key)  # type: ignore[attr-defined]

    def generate_briefing(self, anomalies: list[AnomalyItem]) -> ExecutiveBriefing:
        """Generates executive briefing grounded on detected anomalies using Google Gemini API."""
        if not self._api_key:
            logger.warning("Gemini API key missing. Falling back to deterministic briefing.")
            missing_key_reason = (
                "⚠️ [API KEY EKSİK] Gemini API anahtarı tanımlanmamış. "
                "Pazarlama otomasyonu kural tabanlı deterministik özeti gösterilmektedir."
            )
            return self._build_fallback_briefing(anomalies, reason=missing_key_reason)

        if not anomalies:
            return ExecutiveBriefing(
                summary="No anomalies detected for the target date period.",
                raw_markdown="# Executive Briefing\n\nNo anomalies detected.",
                critical_findings=[],
                recommended_actions=[],
            )

        rendered_prompt = self._prompt_loader.render_prompt(anomalies)

        try:
            model = genai.GenerativeModel(self._model_name)  # type: ignore[attr-defined]
            generation_config = genai.types.GenerationConfig(
                temperature=0.0,
                top_p=0.95,
                max_output_tokens=4096,
            )

            response = model.generate_content(
                rendered_prompt,
                generation_config=generation_config,
            )

            raw_text = response.text if response.text else ""

            if not raw_text:
                logger.error("Gemini API returned an empty response.")
                empty_reason = (
                    "⚠️ [BOŞ YANIT] Gemini AI servisi boş yanıt döndürdü. "
                    "Kural tabanlı deterministik özet gösterilmektedir."
                )
                return self._build_fallback_briefing(anomalies, reason=empty_reason)

            # Deterministic post-validation cross-examining against source anomalies
            is_valid, discrepancies, validated_markdown = self._validator.validate(
                raw_text, anomalies, strict=False
            )

            if not is_valid:
                logger.warning(
                    f"Gemini briefing failed strict validation. Found {len(discrepancies)} issues."
                )

            summary = self._extract_summary(validated_markdown)
            critical_findings = [
                a.rationale for a in anomalies if a.severity.value in ("critical", "high")
            ]
            recommended_actions = self._extract_recommended_actions(validated_markdown)
            if not recommended_actions:
                recommended_actions = [
                    "Kritik CPA artışı veya ROAS düşüşü olan kampanyaların bütçelerini denetleyin.",
                    "Kreatif performanslarını ve açılış sayfalarını kontrol edin.",
                    "Dönüşüm ilişkilendirme ve piksel izleme sistemlerini doğrulayın.",
                ]

            return ExecutiveBriefing(
                summary=summary,
                raw_markdown=validated_markdown,
                critical_findings=critical_findings,
                recommended_actions=recommended_actions,
            )

        except Exception as err:
            err_str = str(err).lower()
            logger.error(f"Google Gemini API error: {err}. Falling back to deterministic briefing.")
            if (
                "429" in err_str
                or "quota" in err_str
                or "rate_limit" in err_str
                or "resource_exhausted" in err_str
            ):
                reason = (
                    "⚠️ [API LİMİTİ AŞILDI (HTTP 429)] Google Gemini kota sınırına ulaşıldı. "
                    "Lütfen 1 dakika sonra tekrar deneyin."
                )
            elif (
                "api_key" in err_str
                or "unauthorized" in err_str
                or "401" in err_str
                or "invalid" in err_str
            ):
                reason = (
                    "⚠️ [GEÇERSİZ API KEY (HTTP 401)] Gemini API anahtarı doğrulanamadı. "
                    "Kural tabanlı yedek özet gösterilmektedir."
                )
            else:
                reason = (
                    "⚠️ [LLM SERVİSİ YANIT VEREMEDİ] Gemini AI bağlantısı kurulamadı. "
                    "Kural tabanlı yedek özet gösterilmektedir."
                )

            return self._build_fallback_briefing(anomalies, reason=reason)

    def _extract_summary(self, markdown_text: str) -> str:
        """Extracts executive summary paragraph from generated markdown."""
        lines = markdown_text.splitlines()
        in_summary = False
        summary_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            header_clean = stripped.lstrip("#* ").strip().lower()
            if (
                header_clean
                in (
                    "executive summary",
                    "yönetici özeti",
                    "özet",
                    "executive briefing",
                    "yönetici brifingi",
                )
                or header_clean.startswith("executive summary")
                or (header_clean.startswith("yönetici özeti"))
            ):
                in_summary = True
                continue
            if in_summary and stripped.startswith("#"):
                break
            if in_summary and stripped:
                summary_lines.append(stripped)

        if summary_lines:
            raw_sum = " ".join(summary_lines)
        else:
            # Fallback to first non-header paragraph if header parser didn't match
            non_header_paragraphs = [
                p.strip()
                for p in markdown_text.split("\n\n")
                if p.strip() and not p.strip().startswith("#")
            ]
            if non_header_paragraphs:
                raw_sum = non_header_paragraphs[0]
            else:
                return (
                    "⚠️ [KURAL TABANLI YEDEK] Gemini LLM servisi yanıt veremedi. "
                    "Pazarlama otomasyonu deterministik özeti gösterilmektedir."
                )

        # Sanitize raw markdown bullet/bold tags like "- **Özet:**"
        cleaned_lines: list[str] = []
        for line in raw_sum.splitlines():
            s = line.strip()
            if s.startswith("- **") or s.startswith("* **"):
                parts = s.split("**", 2)
                if len(parts) >= 3:
                    s = parts[2].lstrip(": ").strip()
            elif s.startswith("- ") or s.startswith("* "):
                s = s[2:].strip()
            if s:
                cleaned_lines.append(s)

        return " ".join(cleaned_lines) if cleaned_lines else raw_sum

    def _extract_recommended_actions(self, markdown_text: str) -> list[str]:
        """Extracts recommended actions bullet points from generated markdown."""
        lines = markdown_text.splitlines()
        in_actions = False
        action_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            header_clean = stripped.lstrip("#* ").strip().lower()
            if (
                "recommended action" in header_clean
                or "önerilen aksiyon" in header_clean
                or "aksiyonlar" in header_clean
            ):
                in_actions = True
                continue
            if in_actions and stripped.startswith("#"):
                break
            if in_actions and stripped:
                if (
                    stripped.startswith("- ")
                    or stripped.startswith("* ")
                    or stripped.startswith("• ")
                ):
                    action_lines.append(stripped.lstrip("-*• ").strip())
                elif stripped:
                    action_lines.append(stripped)

        return action_lines

    def _build_fallback_briefing(
        self, anomalies: list[AnomalyItem], reason: str | None = None
    ) -> ExecutiveBriefing:
        """Constructs deterministic fallback briefing when LLM service is unavailable."""
        critical_count = sum(1 for a in anomalies if a.severity.value in ("critical", "high"))
        total_count = len(anomalies)

        default_reason = (
            f"⚠️ [DETERMİNİSTİK YEDEK - LLM DEVRE DIŞI] Toplam {total_count} "
            f"istatistiksel anomali ({critical_count} kritik/yüksek) tespit edilmiştir."
        )
        summary = reason or default_reason

        critical_lines = [
            f"- Kampanya '{a.campaign_name}' ({a.platform.value}): {a.rationale}" for a in anomalies
        ]
        critical_text = (
            "\n".join(critical_lines) if critical_lines else "- Kritik anomali tespit edilmedi."
        )

        actions = [
            "Kritik CPA artışı veya ROAS düşüşü olan kampanyaların günlük bütçelerini denetleyin.",
            "Kreatif performanslarını ve açılış sayfalarını kontrol edin.",
            "Dönüşüm ilişkilendirme ve piksel izleme sistemlerini doğrulayın.",
        ]

        markdown_content = f"""# Yönetici Brifingi (Deterministik Yedek)

## Yönetici Özeti
{summary}

## Kritik Anomaliler
{critical_text}

## Olumlu Sinyaller
- Bu dönemde olumlu anomali sinyali tespit edilmemiştir.

## Önerilen Aksiyonlar
{chr(10).join(f"- {act}" for act in actions)}
"""

        return ExecutiveBriefing(
            summary=summary,
            raw_markdown=markdown_content,
            critical_findings=[
                a.rationale for a in anomalies if a.severity.value in ("critical", "high")
            ],
            recommended_actions=actions,
        )
