import logging
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx

from src.agent.schemas.reasoning import BatchAnalysisResult
from src.application.ports.notification import INotificationService
from src.domain.models.briefing import ExecutiveBriefing
from src.domain.models.evidence_dossier import EvidenceDossier
from src.infrastructure.config.settings import get_settings
from src.infrastructure.reporting.localization import (
    localize_action_label,
    localize_issue_type,
    localize_severity,
)

logger = logging.getLogger(__name__)

_HEALTH_EMOJI: dict[str, str] = {
    "HEALTHY": "🟢",
    "DEGRADED": "🟡",
    "CRITICAL": "🔴",
}

_SEVERITY_EMOJI: dict[str, str] = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "MEDIUM": "🟡",
    "LOW": "🟢",
}


class SlackNotificationService(INotificationService):
    """Slack notification service implementation using HTTPX and Slack Block Kit format."""

    def __init__(
        self,
        webhook_url: str | None = None,
        timeout: float = 10.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self._webhook_url: str = settings.slack_webhook_url if webhook_url is None else webhook_url
        self._timeout: float = timeout
        self._http_client: httpx.Client | None = http_client

    def send(self, briefing: ExecutiveBriefing) -> bool:
        """Dispatches an executive briefing to Slack webhook using Block Kit format."""
        return self.send_briefing(briefing=briefing)

    def send_briefing(
        self,
        briefing: ExecutiveBriefing | None = None,
        dossier: EvidenceDossier | None = None,
        result: BatchAnalysisResult | None = None,
    ) -> bool:
        """Dispatches a dynamic marketing anomaly briefing to Slack webhook.

        Supports both BatchAnalysisResult (agentic flow) and ExecutiveBriefing (legacy flow).
        """
        if not self._webhook_url:
            logger.warning("Slack notification skipped: SLACK_WEBHOOK_URL is not configured.")
            return False

        if result is not None:
            payload = self.build_agent_briefing_block_kit(result=result, dossier=dossier)
        elif briefing is not None:
            payload = self.build_briefing_block_kit(briefing=briefing)
        else:
            logger.warning("Slack notification skipped: neither result nor briefing provided.")
            return False

        return self._post_payload(payload)

    def build_agent_briefing_block_kit(
        self,
        result: BatchAnalysisResult,
        dossier: EvidenceDossier | None = None,
    ) -> dict[str, object]:
        """Constructs dynamic Slack Block Kit payload from BatchAnalysisResult & dossier.

        Args:
            result: Gemini agent BatchAnalysisResult with verified diagnoses & action plans.
            dossier: Optional statistical EvidenceDossier entity.

        Returns:
            Structured Block Kit payload dictionary with zero raw enum strings.
        """
        health_status = (result.overall_data_health or "HEALTHY").upper()
        health_badge = _HEALTH_EMOJI.get(health_status, "🟡")

        target_date = dossier.target_date if dossier and dossier.target_date else "Bugün"

        blocks: list[dict[str, object]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📢 Günlük Reklam Operasyon Brifingi | {target_date} {health_badge}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Yönetici Özeti:*\n{result.executive_summary}",
                },
            },
            {"type": "divider"},
        ]

        # Dynamic Top Findings Blocks (up to 3 findings)
        for idx, finding in enumerate(result.findings[:3], start=1):
            issue_badge = localize_issue_type(finding.issue_type)

            confidence_pct = round(finding.confidence_score * 100)

            finding_header = (
                f"*{idx}. {finding.campaign_name}* ({finding.platform} - {finding.country})\n"
                f"📌 *Teşhis:* `{issue_badge}` | *Güven:* %{confidence_pct}\n"
                f"📊 *Metrik Değişimi:* {finding.metric_change_summary}"
            )

            root_cause_text = f"*Kök Neden Analizi:*\n{finding.root_cause_analysis}"

            # Operational action vector breakdown — localized
            action_plan = finding.action_plan
            budget_label = localize_action_label(action_plan.budget_action)
            bid_label = localize_action_label(action_plan.bid_action)
            creative_label = localize_action_label(action_plan.creative_action)
            tracking_label = localize_action_label(action_plan.tracking_action)

            action_vector_text = (
                f"*Operasyonel Aksiyonlar:*\n"
                f"• *Bütçe:* `{budget_label}`\n"
                f"• *Teklif:* `{bid_label}`\n"
                f"• *Kreatif:* `{creative_label}`\n"
                f"• *Takip:* `{tracking_label}`"
            )

            concrete_steps_text = ""
            if action_plan.concrete_steps:
                first_two_steps = action_plan.concrete_steps[:2]
                steps_formatted = "\n".join(
                    f"  {step_idx}. {step}"
                    for step_idx, step in enumerate(first_two_steps, start=1)
                )
                concrete_steps_text = f"\n*Somut Adımlar:*\n{steps_formatted}"

            primary_action = localize_action_label(action_plan.tracking_action)
            if action_plan.tracking_action.upper() in ("NO_CHANGE", "NO_ACTION"):
                primary_action = localize_action_label(action_plan.budget_action)

            finding_body = (
                f"{finding_header}\n\n"
                f"{root_cause_text}\n\n"
                f"{action_vector_text}"
                f"{concrete_steps_text}\n\n"
                f"🛠️ *Öncelikli Aksiyon:* {primary_action}"
            )

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": finding_body,
                    },
                }
            )

            if idx < len(result.findings[:3]):
                blocks.append({"type": "divider"})

        # Context / Footer block
        blocks.append({"type": "divider"})

        anomalies_cnt = dossier.total_anomalies_detected if dossier else len(result.findings)
        spend_at_risk = 0.0
        if dossier:
            spend_at_risk = sum(c.financial_impact_score for c in dossier.top_campaign_evidence)

        timestamp_str = (
            result.analysis_timestamp
            if result.analysis_timestamp
            else datetime.now(UTC).isoformat()
        )

        footer_text = (
            f"🕒 *Zaman:* {timestamp_str} | "
            f"⚡ *Toplam Anomali:* {anomalies_cnt} | "
            f"💰 *Risk Altındaki Harcama:* ${spend_at_risk:,.2f}\n"
            f"📄 *Detaylı Rapor:* `output/top_3_findings.md`"
        )

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": footer_text,
                    }
                ],
            }
        )

        return {"blocks": blocks}

    def build_briefing_block_kit(
        self,
        briefing: ExecutiveBriefing,
        top_3_findings: list[dict[str, str]] | None = None,
    ) -> dict[str, object]:
        """Constructs a Slack Block Kit payload from an ExecutiveBriefing.

        Args:
            briefing: ExecutiveBriefing domain entity.
            top_3_findings: Optional list of finding dicts to render structured findings.
        """
        timestamp_str = briefing.generated_at.isoformat()

        blocks: list[dict[str, object]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 Günlük Yönetici Performans Brifingi",
                    "emoji": True,
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Oluşturulma Zamanı:* {timestamp_str} | *Durum:* Başarılı",
                    }
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Yönetici Özeti:*\n{briefing.summary}",
                },
            },
        ]

        if top_3_findings:
            findings_blocks = self.build_findings_block_kit(top_3_findings)
            blocks.extend(findings_blocks)
        elif briefing.critical_findings:
            findings_text = "\n".join(f"• {finding}" for finding in briefing.critical_findings)
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Önemli Anomaliler ve Kritik Bulgular:*\n{findings_text}",
                    },
                }
            )

        if briefing.recommended_actions:
            actions_text = "\n".join(f"• {action}" for action in briefing.recommended_actions)
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Önerilen Aksiyonlar:*\n{actions_text}",
                    },
                }
            )

        blocks.append({"type": "divider"})
        return {"blocks": blocks}

    @staticmethod
    def build_findings_block_kit(
        findings: list[dict[str, str]],
    ) -> list[dict[str, object]]:
        """Build Slack Block Kit sections for top-3 operational findings."""
        blocks: list[dict[str, object]] = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🎯 En Kritik 3 Operasyonel Bulgu:*",
                },
            },
        ]

        for idx, finding in enumerate(findings, start=1):
            severity = finding.get("severity", "MEDIUM")
            emoji = _SEVERITY_EMOJI.get(severity, "⚪")
            severity_label = localize_severity(severity)
            campaign = finding.get("campaign_name", "Bilinmiyor")
            platform = finding.get("platform", "N/A")
            country = finding.get("country", "N/A")
            metric_change = finding.get("metric_change", "N/A")
            issue_type_raw = finding.get("issue_type", "N/A")
            issue_label = localize_issue_type(issue_type_raw)
            operational_action_raw = finding.get("operational_action", "N/A")
            operational_action = localize_action_label(operational_action_raw)
            score = finding.get("score", "0")

            finding_text = (
                f"{emoji} *Bulgu #{idx}: {campaign}* | {severity_label}\n"
                f"📌 *Platform:* {platform} | *Ülke:* {country} | *Skor:* {score}\n"
                f"📊 *Metrik Değişimi:* {metric_change}\n"
                f"🔍 *Teşhis:* {issue_label}\n"
                f"⚡ *Aksiyon:* {operational_action}"
            )

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": finding_text,
                    },
                }
            )
            if idx < len(findings):
                blocks.append({"type": "divider"})

        return blocks

    def build_failure_alert_block_kit(
        self,
        execution_id: str,
        failed_stage: str,
        error_message: str,
        timestamp: str,
    ) -> dict[str, object]:
        """Constructs a Slack Block Kit emergency alert payload for pipeline failures."""
        blocks: list[dict[str, object]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 KRİTİK UYARI: Pipeline Çalıştırma Başarısız",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Çalıştırma Kimliği:*\n{execution_id}"},
                    {"type": "mrkdwn", "text": "*Kanal:*\n#marketing-alerts-critical"},
                    {"type": "mrkdwn", "text": f"*Başarısız Olan Aşama:*\n{failed_stage}"},
                    {"type": "mrkdwn", "text": f"*Zaman Damgası:*\n{timestamp}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Hata Mesajı:*\n```{error_message}```",
                },
            },
        ]
        return {
            "channel": "#marketing-alerts-critical",
            "blocks": blocks,
        }

    def send_failure_alert(
        self,
        execution_id: str,
        failed_stage: str,
        error_message: str,
        timestamp: str,
    ) -> bool:
        """Sends an emergency alert payload to Slack for pipeline failures."""
        if not self._webhook_url:
            logger.warning("Slack alert skipped: SLACK_WEBHOOK_URL is not configured.")
            return False

        payload = self.build_failure_alert_block_kit(
            execution_id=execution_id,
            failed_stage=failed_stage,
            error_message=error_message,
            timestamp=timestamp,
        )
        return self._post_payload(payload)

    def _post_payload(self, payload: Mapping[str, object]) -> bool:
        """Posts a payload dictionary to the Slack webhook URL."""
        try:
            if self._http_client is not None:
                response = self._http_client.post(
                    self._webhook_url, json=payload, timeout=self._timeout
                )
            else:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(self._webhook_url, json=payload)

            if response.status_code >= 400:
                logger.error(
                    "Slack webhook dispatch failed with status code %d: %s",
                    response.status_code,
                    response.text,
                )
                return False
            return True
        except Exception as err:
            logger.error("Slack notification failed due to network/client error: %s", err)
            return False
