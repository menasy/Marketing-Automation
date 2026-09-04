import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Protocol

from src.application.ports.notification import INotificationService
from src.domain.models.briefing import ExecutiveBriefing
from src.infrastructure.config.settings import get_settings

logger = logging.getLogger(__name__)


class ISMTPTransport(Protocol):
    """Protocol abstraction for sending MIME emails via SMTP."""

    def send_message(
        self,
        message: MIMEMultipart,
        host: str,
        port: int,
        username: str = "",
        password: str = "",
    ) -> None: ...


class DefaultSMTPTransport:
    """Default SMTP transport implementation using standard library smtplib."""

    def send_message(
        self,
        message: MIMEMultipart,
        host: str,
        port: int,
        username: str = "",
        password: str = "",
    ) -> None:
        with smtplib.SMTP(host, port, timeout=10.0) as server:
            if username and password:
                server.starttls()
                server.login(username, password)
            server.send_message(message)


class EmailNotificationService(INotificationService):
    """Email notification dispatcher implementing fallback executive briefing delivery."""

    def __init__(
        self,
        transport: ISMTPTransport | None = None,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        from_email: str | None = None,
        to_email: str | None = None,
    ) -> None:
        settings = get_settings()
        self._transport: ISMTPTransport = transport or DefaultSMTPTransport()
        self._smtp_host: str = smtp_host or settings.smtp_host
        self._smtp_port: int = smtp_port if smtp_port is not None else settings.smtp_port
        self._smtp_username: str = smtp_username or settings.smtp_username
        self._smtp_password: str = smtp_password or settings.smtp_password
        self._from_email: str = from_email or settings.smtp_from_email
        self._to_email: str = to_email or settings.smtp_to_email

    def send(self, briefing: ExecutiveBriefing) -> bool:
        """Dispatches executive briefing email to configured recipients."""
        if not self._smtp_host or not self._from_email or not self._to_email:
            logger.warning("Email notification skipped: SMTP configuration is incomplete.")
            return False

        message = self.build_email_message(briefing)
        try:
            self._transport.send_message(
                message=message,
                host=self._smtp_host,
                port=self._smtp_port,
                username=self._smtp_username,
                password=self._smtp_password,
            )
            return True
        except Exception as err:
            logger.error("Email notification failed to dispatch: %s", err)
            return False

    def build_email_message(self, briefing: ExecutiveBriefing) -> MIMEMultipart:
        """Constructs MIMEMultipart email object containing HTML and plain text bodies."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = (
            f"Executive Performance Briefing - {briefing.generated_at.strftime('%Y-%m-%d')}"
        )
        msg["From"] = self._from_email
        msg["To"] = self._to_email

        text_body = self._build_text_body(briefing)
        html_body = self._build_html_body(briefing)

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        return msg

    def _build_text_body(self, briefing: ExecutiveBriefing) -> str:
        lines = [
            "DAILY EXECUTIVE PERFORMANCE BRIEFING",
            "=" * 40,
            f"Generated At: {briefing.generated_at.isoformat()}",
            "",
            "EXECUTIVE SUMMARY:",
            briefing.summary,
            "",
        ]
        if briefing.critical_findings:
            lines.append("TOP ANOMALIES & CRITICAL FINDINGS:")
            lines.extend(f"• {finding}" for finding in briefing.critical_findings)
            lines.append("")

        if briefing.recommended_actions:
            lines.append("RECOMMENDED ACTIONS:")
            lines.extend(f"• {action}" for action in briefing.recommended_actions)
            lines.append("")

        lines.append("RAW BRIEFING DETAILED REPORT:")
        lines.append(briefing.raw_markdown)
        return "\n".join(lines)

    def _build_html_body(self, briefing: ExecutiveBriefing) -> str:
        findings_html = ""
        if briefing.critical_findings:
            items = "".join(f"<li>{finding}</li>" for finding in briefing.critical_findings)
            findings_html = f"<h3>Critical Findings</h3><ul>{items}</ul>"

        actions_html = ""
        if briefing.recommended_actions:
            items = "".join(f"<li>{action}</li>" for action in briefing.recommended_actions)
            actions_html = f"<h3>Recommended Actions</h3><ul>{items}</ul>"

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
  <h2>📊 Daily Executive Performance Briefing</h2>
  <p><strong>Generated At:</strong> {briefing.generated_at.isoformat()}</p>
  <hr>
  <h3>Executive Summary</h3>
  <p>{briefing.summary}</p>
  {findings_html}
  {actions_html}
</body>
</html>"""
