from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from unittest.mock import MagicMock

import httpx

from src.domain.models.briefing import ExecutiveBriefing
from src.infrastructure.notifications.email import EmailNotificationService, ISMTPTransport
from src.infrastructure.notifications.slack import SlackNotificationService


def create_sample_briefing() -> ExecutiveBriefing:
    """Creates a sample ExecutiveBriefing instance for testing."""
    return ExecutiveBriefing(
        summary="ROAS increased by 15% across Google Ads campaigns.",
        raw_markdown="# Executive Briefing\nROAS up 15%.",
        critical_findings=[
            "Google Ads CPC spiked +2.5 z-score",
            "Meta Ads impressions dropped -3.1 z-score",
        ],
        recommended_actions=[
            "Reallocate budget to high-performing Google Ads",
            "Audit Meta Ads targeting",
        ],
        generated_at=datetime(2026, 9, 4, 8, 0, 0, tzinfo=UTC),
    )


class MockSMTPTransport(ISMTPTransport):
    """Mock SMTP transport for testing email dispatcher."""

    def __init__(self) -> None:
        self.sent_messages: list[tuple[MIMEMultipart, str, int, str, str]] = []
        self.should_fail: bool = False

    def send_message(
        self,
        message: MIMEMultipart,
        host: str,
        port: int,
        username: str = "",
        password: str = "",
    ) -> None:
        if self.should_fail:
            raise RuntimeError("SMTP Server connection failed")
        self.sent_messages.append((message, host, port, username, password))


# --- Slack Notification Tests ---


def test_slack_send_success() -> None:
    """Verifies successful Slack Block Kit notification dispatch via HTTPX."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_client.post.return_value = mock_response

    webhook_url = "https://hooks.slack.com/services/TEST/WEBHOOK/123"
    service = SlackNotificationService(webhook_url=webhook_url, http_client=mock_client)
    briefing = create_sample_briefing()

    success = service.send(briefing)

    assert success is True
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == webhook_url
    json_body = call_args[1]["json"]
    assert "blocks" in json_body
    assert len(json_body["blocks"]) >= 4


def test_slack_block_kit_json_validity() -> None:
    """Verifies that Slack Block Kit structure contains all required sections."""
    service = SlackNotificationService(webhook_url="https://hooks.slack.com/test")
    briefing = create_sample_briefing()

    payload = service.build_briefing_block_kit(briefing)
    blocks = payload["blocks"]
    assert isinstance(blocks, list)

    header_block = blocks[0]
    assert header_block["type"] == "header"

    # Check for summary and findings in blocks
    block_texts = [
        block["text"]["text"]
        for block in blocks
        if "text" in block and isinstance(block["text"], dict) and "text" in block["text"]
    ]
    summary_found = any("ROAS increased" in text for text in block_texts)
    findings_found = any("Google Ads CPC" in text for text in block_texts)

    assert summary_found is True
    assert findings_found is True


def test_slack_failure_alert_formatting() -> None:
    """Verifies emergency failure alert Block Kit formatting and delivery."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_client.post.return_value = mock_response

    webhook_url = "https://hooks.slack.com/services/TEST/WEBHOOK/CRITICAL"
    service = SlackNotificationService(webhook_url=webhook_url, http_client=mock_client)

    success = service.send_failure_alert(
        execution_id="exec-12345",
        failed_stage="Anomaly Detection Stage",
        error_message="Insufficient data rows for baseline window",
        timestamp="2026-09-04T08:00:00Z",
    )

    assert success is True
    json_body = mock_client.post.call_args[1]["json"]
    assert json_body["channel"] == "#marketing-alerts-critical"
    blocks = json_body["blocks"]
    alert_header_found = any(
        "🚨 CRITICAL ALERT" in b.get("text", {}).get("text", "") for b in blocks if "text" in b
    )
    assert alert_header_found is True


def test_slack_send_http_error() -> None:
    """Verifies defensive error handling when Slack webhook returns an HTTP error status."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_client.post.return_value = mock_response

    service = SlackNotificationService(
        webhook_url="https://hooks.slack.com/test", http_client=mock_client
    )
    briefing = create_sample_briefing()

    success = service.send(briefing)
    assert success is False


def test_slack_send_missing_webhook_url() -> None:
    """Verifies that sending skips gracefully when webhook URL is missing."""
    service = SlackNotificationService(webhook_url="")
    briefing = create_sample_briefing()

    success = service.send(briefing)
    assert success is False


# --- Email Notification Tests ---


def test_email_send_success() -> None:
    """Verifies email dispatch functionality using mock SMTP transport."""
    mock_transport = MockSMTPTransport()
    service = EmailNotificationService(
        transport=mock_transport,
        smtp_host="mail.example.com",
        smtp_port=587,
        from_email="sender@example.com",
        to_email="receiver@example.com",
    )
    briefing = create_sample_briefing()

    success = service.send(briefing)

    assert success is True
    assert len(mock_transport.sent_messages) == 1
    msg, host, port, _, _ = mock_transport.sent_messages[0]
    assert host == "mail.example.com"
    assert port == 587
    assert msg["From"] == "sender@example.com"
    assert msg["To"] == "receiver@example.com"
    assert "Executive Performance Briefing" in msg["Subject"]


def test_email_send_smtp_error() -> None:
    """Verifies defensive error handling when SMTP transport raises an exception."""
    mock_transport = MockSMTPTransport()
    mock_transport.should_fail = True
    service = EmailNotificationService(
        transport=mock_transport,
        smtp_host="mail.example.com",
        from_email="sender@example.com",
        to_email="receiver@example.com",
    )
    briefing = create_sample_briefing()

    success = service.send(briefing)
    assert success is False


def test_email_send_missing_config() -> None:
    """Verifies that email notification returns False when mandatory configuration is missing."""
    service = EmailNotificationService(
        smtp_host="",
        from_email="",
        to_email="",
    )
    briefing = create_sample_briefing()

    success = service.send(briefing)
    assert success is False


def test_slack_build_findings_block_kit_renders_structured_findings() -> None:
    """Verifies that build_findings_block_kit renders emojis, campaign data, and actions."""
    findings: list[dict[str, str]] = [
        {
            "campaign_name": "US_Search_Brand",
            "platform": "google_ads",
            "country": "US",
            "metric_change": "CONVERSIONS: 140.00 → 0.00 (-100%) | SPEND: $1,200 → $1,200 (+0%)",
            "issue_type": "VERİ / TRACKING HATASI",
            "operational_action": (
                "Google Ads CAPI/Pixel entegrasyonunu kontrol edin, bütçeyi kapatmayın."
            ),
            "severity": "CRITICAL",
            "score": "245.5",
        },
        {
            "campaign_name": "EU_Retargeting_Meta",
            "platform": "meta_ads",
            "country": "DE",
            "metric_change": "CTR: 0.03 → 0.01 (-75%) | CPA: $25 → $65 (+160%)",
            "issue_type": "GERÇEK PERFORMANS SORUNU",
            "operational_action": "Günlük bütçeyi %20 kısın, yıpranmış kreatifleri yenileyin.",
            "severity": "HIGH",
            "score": "180.0",
        },
    ]

    blocks = SlackNotificationService.build_findings_block_kit(findings)
    assert isinstance(blocks, list)
    assert len(blocks) >= 3  # header + 2 findings + divider

    # Verify severity emojis are present
    all_text = " ".join(
        str(block.get("text", {}).get("text", ""))
        for block in blocks
        if isinstance(block.get("text"), dict)
    )
    assert "🔴" in all_text  # CRITICAL emoji
    assert "🟠" in all_text  # HIGH emoji
    assert "US_Search_Brand" in all_text
    assert "EU_Retargeting_Meta" in all_text
    assert "CONVERSIONS" in all_text
    assert "VERİ / TRACKING HATASI" in all_text
    assert "GERÇEK PERFORMANS SORUNU" in all_text
    assert "bütçeyi" in all_text.lower()


def test_slack_briefing_with_top_3_findings_overrides_generic() -> None:
    """Verifies that build_briefing_block_kit uses structured findings when provided."""
    service = SlackNotificationService(webhook_url="https://hooks.slack.com/test")
    briefing = create_sample_briefing()

    findings: list[dict[str, str]] = [
        {
            "campaign_name": "TestCampaign",
            "platform": "google_ads",
            "country": "US",
            "metric_change": "CPA: $30 → $90 (+200%)",
            "issue_type": "GERÇEK PERFORMANS SORUNU",
            "operational_action": "Günlük bütçeyi %20 kısın.",
            "severity": "HIGH",
            "score": "150.0",
        },
    ]

    payload = service.build_briefing_block_kit(briefing, top_3_findings=findings)
    blocks = payload["blocks"]

    # The structured finding should appear instead of generic critical_findings
    all_text = " ".join(
        str(block.get("text", {}).get("text", ""))
        for block in blocks
        if isinstance(block.get("text"), dict)
    )
    assert "TestCampaign" in all_text
    assert "CPA" in all_text
    assert "bütçeyi" in all_text.lower()
    # Generic findings should NOT appear when top_3_findings are provided
    assert "Google Ads CPC spiked" not in all_text
