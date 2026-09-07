"""Unit tests for dynamic Slack Block Kit notification payload composition and HTTP dispatching."""

from unittest.mock import MagicMock

import httpx

from src.agent.schemas.reasoning import (
    BatchAnalysisResult,
    DiagnosedFinding,
    Hypothesis,
    OperationalActionPlan,
)
from src.domain.models.evidence_dossier import (
    CampaignEvidence,
    EvidenceDossier,
    MetricEvidence,
)
from src.infrastructure.notifications.slack import SlackNotificationService


def create_sample_batch_result(health: str = "HEALTHY") -> BatchAnalysisResult:
    """Helper to construct a realistic BatchAnalysisResult for testing."""
    finding_1 = DiagnosedFinding(
        campaign_name="US_Search_Brand",
        platform="google_ads",
        country="US",
        issue_type="DATA_QUALITY",
        confidence_score=0.95,
        root_cause_analysis=(
            "Conversion tracking breakdown detected. Spend steady while conversions dropped 100%."
        ),
        competing_hypotheses=[
            Hypothesis(
                statement="Google Ads Conversion Tag missing",
                confidence=0.95,
            )
        ],
        selected_hypothesis=Hypothesis(
            statement="Google Ads Conversion Tag missing",
            confidence=0.95,
        ),
        action_plan=OperationalActionPlan(
            budget_action="HOLD_CURRENT_BUDGET",
            bid_action="NO_CHANGE",
            creative_action="NO_CHANGE",
            tracking_action="VERIFY_GOOGLE_CONVERSION_TAG",
            rationale="Do not alter ad delivery until tag is verified.",
            concrete_steps=[
                "Inspect GTM container for Conversion Linker trigger.",
                "Verify Google Ads Conversion Tag purchase event fire.",
            ],
            expected_effect="Restore conversion tracking signal.",
            risk_level="LOW",
            requires_approval=False,
        ),
        metric_change_summary="Conversions: 150 → 0 (-100%), Spend: $500",
        business_impact_narrative="Data tracking breakdown hiding real conversions.",
    )

    finding_2 = DiagnosedFinding(
        campaign_name="DE_Retargeting_Sales",
        platform="meta_ads",
        country="DE",
        issue_type="PERFORMANCE",
        confidence_score=0.88,
        root_cause_analysis="Ad creative fatigue causing sharp CTR collapse and CPA spike.",
        competing_hypotheses=[
            Hypothesis(
                statement="Creative saturation and ad fatigue",
                confidence=0.88,
            )
        ],
        selected_hypothesis=Hypothesis(
            statement="Creative saturation and ad fatigue",
            confidence=0.88,
        ),
        action_plan=OperationalActionPlan(
            budget_action="REDUCE_BUDGET_30_PERCENT",
            bid_action="CAP_TARGET_CPA",
            creative_action="ROTATE_FATIGUED_CREATIVES",
            tracking_action="NO_CHANGE",
            rationale="Reduce spend wastage on fatigued audience.",
            concrete_steps=[
                "Pause top fatigued video creative variation.",
                "Launch new lifestyle image creative set.",
            ],
            expected_effect="Improve CTR and lower CPA.",
            risk_level="MEDIUM",
            requires_approval=True,
        ),
        metric_change_summary="CTR: 2.5% → 0.8% (-68%), CPA: €20 → €65 (+225%)",
        business_impact_narrative="High CPA driving overall account inefficiency.",
    )

    return BatchAnalysisResult(
        findings=[finding_1, finding_2],
        executive_summary=(
            "Executive Summary: Total 2 critical findings identified across US and DE campaigns."
        ),
        overall_data_health=health,
        analysis_timestamp="2026-09-07T12:00:00Z",
    )


def create_sample_dossier() -> EvidenceDossier:
    """Helper to construct a realistic EvidenceDossier for testing."""
    metric = MetricEvidence(
        metric_name="CONVERSIONS",
        current_value=0.0,
        baseline_value=150.0,
        delta_pct=-100.0,
        z_score=-4.5,
        is_anomaly=True,
    )
    evidence_1 = CampaignEvidence(
        campaign_id="c1",
        campaign_name="US_Search_Brand",
        platform="google_ads",
        account_id="act_google_us",
        country="US",
        spend=500.0,
        financial_impact_score=2250.0,
        metrics={"CONVERSIONS": metric},
    )
    evidence_2 = CampaignEvidence(
        campaign_id="c2",
        campaign_name="DE_Retargeting_Sales",
        platform="meta_ads",
        account_id="act_meta_de",
        country="DE",
        spend=300.0,
        financial_impact_score=1200.0,
        metrics={"CTR": metric},
    )
    return EvidenceDossier(
        target_date="2026-09-07",
        baseline_window="14-day rolling window",
        total_anomalies_detected=2,
        total_campaigns_impacted=2,
        top_campaign_evidence=(evidence_1, evidence_2),
    )


class TestSlackBlockKitNotificationService:
    """Unit tests for Slack Block Kit payload composition and dispatching."""

    def test_build_agent_briefing_block_kit_structure(self) -> None:
        """Verify dynamic Block Kit payload structure, badges, metrics, and context."""
        url = "https://hooks.slack.com/services/test/test"
        service = SlackNotificationService(webhook_url=url)
        result = create_sample_batch_result(health="HEALTHY")
        dossier = create_sample_dossier()

        payload = service.build_agent_briefing_block_kit(result=result, dossier=dossier)
        assert "blocks" in payload
        blocks = payload["blocks"]
        assert isinstance(blocks, list)

        # 1. Header block assertion
        header = blocks[0]
        assert header["type"] == "header"
        assert "2026-09-07" in header["text"]["text"]
        assert "🟢" in header["text"]["text"]

        # 2. Executive Summary section assertion
        summary_section = blocks[1]
        assert summary_section["type"] == "section"
        assert "Executive Summary:" in summary_section["text"]["text"]

        # 3. Findings blocks assertion
        payload_str = str(blocks)

        # Issue Badges check
        assert "[VERİ / TRACKING HATASI]" in payload_str
        assert "[GERÇEK PERFORMANS DÜŞÜŞÜ]" in payload_str

        # Confidence scores check
        assert "%95" in payload_str
        assert "%88" in payload_str

        # Campaign details check
        assert "US_Search_Brand" in payload_str
        assert "DE_Retargeting_Sales" in payload_str

        # Concrete action steps check
        assert "Inspect GTM container" in payload_str
        assert "Pause top fatigued video creative" in payload_str

        # 4. Context / Footer block check
        footer_block = blocks[-1]
        assert footer_block["type"] == "context"
        footer_text = footer_block["elements"][0]["text"]
        assert "2026-09-07T12:00:00Z" in footer_text
        assert "Spend at Risk" in footer_text
        assert "$3,450.00" in footer_text

    def test_send_briefing_dispatches_http_post(self) -> None:
        """Verify send_briefing dispatches payload via mock HTTP client."""
        mock_http_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_http_client.post.return_value = mock_response

        webhook_url = "https://hooks.slack.com/services/mock/webhook/123"
        service = SlackNotificationService(
            webhook_url=webhook_url,
            http_client=mock_http_client,
        )

        result = create_sample_batch_result()
        dossier = create_sample_dossier()

        success = service.send_briefing(dossier=dossier, result=result)
        assert success is True

        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert call_args[0][0] == webhook_url
        assert "json" in call_args[1]
        payload = call_args[1]["json"]
        assert "blocks" in payload
