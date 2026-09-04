from unittest.mock import MagicMock, patch

from src.domain.enums.metric_type import MetricDirection, MetricType
from src.domain.enums.platform import Platform
from src.domain.enums.severity import Severity
from src.domain.models.anomaly import AnomalyItem
from src.infrastructure.llm.gemini_service import GeminiService


def test_gemini_service_fallback_when_api_key_missing() -> None:
    service = GeminiService(api_key="")
    anomalies = [
        AnomalyItem(
            campaign_name="Test Campaign",
            platform=Platform.GOOGLE_ADS,
            country="US",
            metric=MetricType.CPA,
            current_value=50.0,
            baseline_value=20.0,
            change_rate=1.5,
            z_score=3.5,
            severity=Severity.CRITICAL,
            direction=MetricDirection.LOWER_IS_BETTER,
            detection_method="z_score",
            rationale="CPA spiked by +150%",
        )
    ]
    briefing = service.generate_briefing(anomalies)
    assert briefing.summary is not None
    assert "Brifing" in briefing.raw_markdown or "Briefing" in briefing.raw_markdown


@patch("google.generativeai.GenerativeModel")
def test_gemini_service_generate_briefing_success(mock_model_cls: MagicMock) -> None:
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        "# Executive Briefing\n\n## Executive Summary\n"
        "CPA spiked on Test Campaign.\n\n## Critical Anomalies\n- Test Campaign"
    )
    mock_model.generate_content.return_value = mock_response
    mock_model_cls.return_value = mock_model

    service = GeminiService(api_key="fake-gemini-key")
    anomalies = [
        AnomalyItem(
            campaign_name="Test Campaign",
            platform=Platform.GOOGLE_ADS,
            country="US",
            metric=MetricType.CPA,
            current_value=50.0,
            baseline_value=20.0,
            change_rate=1.5,
            z_score=3.5,
            severity=Severity.CRITICAL,
            direction=MetricDirection.LOWER_IS_BETTER,
            detection_method="z_score",
            rationale="CPA spiked by +150%",
        )
    ]

    briefing = service.generate_briefing(anomalies)
    assert "Executive Summary" in briefing.raw_markdown
    assert briefing.summary is not None
