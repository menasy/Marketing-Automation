import logging
from collections.abc import Mapping

import httpx

from src.application.ports.notification import INotificationService
from src.domain.models.briefing import ExecutiveBriefing
from src.infrastructure.config.settings import get_settings

logger = logging.getLogger(__name__)

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
        if not self._webhook_url:
            logger.warning("Slack notification skipped: SLACK_WEBHOOK_URL is not configured.")
            return False

        payload = self.build_briefing_block_kit(briefing)
        return self._post_payload(payload)

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

        # Inject structured top-3 findings if available (overrides generic findings)
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
        """Build Slack Block Kit sections for top-3 operational findings.

        Args:
            findings: List of finding dicts with keys: campaign_name, platform,
                country, metric_change, issue_type, operational_action, severity, score.

        Returns:
            List of Slack Block Kit block dicts to be appended to the message blocks.
        """
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
            # Add divider between findings but not after the last one
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
