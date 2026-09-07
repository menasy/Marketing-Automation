import logging
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx

from src.agent.schemas.reasoning import BatchAnalysisResult
from src.application.ports.notification import INotificationService
from src.domain.models.briefing import ExecutiveBriefing
from src.domain.models.evidence_dossier import EvidenceDossier
from src.infrastructure.config.settings import get_settings

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
            Structured Block Kit payload dictionary with zero static strings.
        """
        health_status = (result.overall_data_health or "HEALTHY").upper()
        health_badge = _HEALTH_EMOJI.get(health_status, "🟡")

        target_date = dossier.target_date if dossier and dossier.target_date else "Today"

        blocks: list[dict[str, object]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 Marketing Anomaly Briefing | {target_date} {health_badge}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Executive Summary:*\n{result.executive_summary}",
                },
            },
            {"type": "divider"},
        ]

        # Dynamic Top Findings Blocks (up to 3 findings)
        for idx, finding in enumerate(result.findings[:3], start=1):
            issue_raw = finding.issue_type.upper()
            if "DATA" in issue_raw or "TRACKING" in issue_raw or "VERİ" in issue_raw:
                issue_badge = "[VERİ / TRACKING HATASI]"
            else:
                issue_badge = "[GERÇEK PERFORMANS DÜŞÜŞÜ]"

            confidence_pct = round(finding.confidence_score * 100)

            finding_header = (
                f"*{idx}. {finding.campaign_name}* ({finding.platform} - {finding.country})\n"
                f"📌 *Teşhis:* `{issue_badge}` | *Güven:* %{confidence_pct}\n"
                f"📊 *Metrik Değişimi:* {finding.metric_change_summary}"
            )

            root_cause_text = f"*Kök Neden Analizi:*\n{finding.root_cause_analysis}"

            # Operational action vector breakdown
            action_plan = finding.action_plan
            action_vector_text = (
                f"*Operasyonel Aksiyonlar:*\n"
                f"• *Bütçe:* `{action_plan.budget_action}`\n"
                f"• *Teklif:* `{action_plan.bid_action}`\n"
                f"• *Kreatif:* `{action_plan.creative_action}`\n"
                f"• *Takip:* `{action_plan.tracking_action}`"
            )

            concrete_steps_text = ""
            if action_plan.concrete_steps:
                first_two_steps = action_plan.concrete_steps[:2]
                steps_formatted = "\n".join(
                    f"  {step_idx}. {step}"
                    for step_idx, step in enumerate(first_two_steps, start=1)
                )
                concrete_steps_text = f"\n*Somut Adımlar:*\n{steps_formatted}"

            finding_body = (
                f"{finding_header}\n\n"
                f"{root_cause_text}\n\n"
                f"{action_vector_text}"
                f"{concrete_steps_text}"
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
            f"💰 *Spend at Risk:* ${spend_at_risk:,.2f}\n"
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
                    "text": "📊 Daily Executive Performance Briefing",
                    "emoji": True,
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Generated At:* {timestamp_str} | *Status:* Success",
                    }
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Executive Summary:*\n{briefing.summary}",
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
                        "text": f"*Top Anomalies & Critical Findings:*\n{findings_text}",
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
                        "text": f"*Recommended Actions:*\n{actions_text}",
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
                    "text": "*🎯 Top 3 Kritik Operasyonel Bulgular:*",
                },
            },
        ]

        for idx, finding in enumerate(findings, start=1):
            severity = finding.get("severity", "MEDIUM")
            emoji = _SEVERITY_EMOJI.get(severity, "⚪")
            campaign = finding.get("campaign_name", "Unknown")
            platform = finding.get("platform", "N/A")
            country = finding.get("country", "N/A")
            metric_change = finding.get("metric_change", "N/A")
            issue_type = finding.get("issue_type", "N/A")
            operational_action = finding.get("operational_action", "N/A")
            score = finding.get("score", "0")

            finding_text = (
                f"{emoji} *Bulgu #{idx}: {campaign}*\n"
                f"📌 *Platform:* {platform} | *Ülke:* {country} | *Skor:* {score}\n"
                f"📊 *Metrik Değişimi:* {metric_change}\n"
                f"🔍 *Teşhis:* {issue_type}\n"
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
                    "text": "🚨 CRITICAL ALERT: Pipeline Execution Failed",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Execution ID:*\n{execution_id}"},
                    {"type": "mrkdwn", "text": "*Channel:*\n#marketing-alerts-critical"},
                    {"type": "mrkdwn", "text": f"*Failed Stage:*\n{failed_stage}"},
                    {"type": "mrkdwn", "text": f"*Timestamp:*\n{timestamp}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error Message:*\n```{error_message}```",
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
