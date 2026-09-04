import json
from pathlib import Path
from unittest.mock import MagicMock

from src.application.use_cases.generate_briefing import GenerateBriefingUseCase
from src.domain.enums import MetricDirection, MetricType, Platform, Severity
from src.domain.exceptions import LLMServiceError
from src.domain.models import AnomalyItem, ExecutiveBriefing
from src.infrastructure.config.settings import get_settings


def load_sample_anomalies() -> list[AnomalyItem]:
    """Loads sample anomalies from output/anomalies.json or creates fallback entities."""
    settings = get_settings()
    anomalies_file = settings.output_dir / "anomalies.json"

    if anomalies_file.is_file():
        raw_data = json.loads(anomalies_file.read_text(encoding="utf-8"))
        items: list[AnomalyItem] = []
        for d in raw_data[:5]:  # Take first 5 for integration test
            is_valid_plat = d["platform"] in ("google_ads", "meta_ads")
            p_val = Platform(d["platform"]) if is_valid_plat else Platform.GOOGLE_ADS
            m_str = d["metric"].lower()
            m_types = [m.value for m in MetricType]
            m_val = MetricType(m_str) if m_str in m_types else MetricType.SPEND
            s_str = d["severity"].lower()
            s_types = [s.value for s in Severity]
            s_val = Severity(s_str) if s_str in s_types else Severity.HIGH
            dir_val = (
                MetricDirection.LOWER_IS_BETTER
                if "cpa" in m_str
                else MetricDirection.HIGHER_IS_BETTER
            )

            items.append(
                AnomalyItem(
                    campaign_name=d["campaign"],
                    platform=p_val,
                    country=d["country"],
                    metric=m_val,
                    current_value=float(d["current_value"]),
                    baseline_value=float(d["baseline_value"]),
                    change_rate=float(d["change_rate"]),
                    z_score=float(d["z_score"]),
                    severity=s_val,
                    direction=dir_val,
                    detection_method=d.get("detection_method", "rolling_zscore"),
                    rationale=d.get("rationale", ""),
                )
            )
        return items

    return [
        AnomalyItem(
            campaign_name="AH | Search | Generic",
            platform=Platform.GOOGLE_ADS,
            country="UK",
            metric=MetricType.CPA,
            current_value=81.67,
            baseline_value=28.34,
            change_rate=1.882,
            z_score=8.46,
            severity=Severity.CRITICAL,
            direction=MetricDirection.LOWER_IS_BETTER,
            detection_method="rolling_zscore",
            rationale="CPA spiked by +188.2%",
        )
    ]


def test_generate_briefing_use_case_end_to_end(tmp_path: Path) -> None:
    """Verify GenerateBriefingUseCase workflow with mock LLM service and markdown export."""
    anomalies = load_sample_anomalies()
    first_camp = anomalies[0].campaign_name

    mock_markdown = f"""# Executive Briefing

## Executive Summary
Evaluation identified 5 critical performance anomalies across Google Ads and Meta Ads.

## Critical Anomalies
- Campaign '{first_camp}' experienced a significant CPA spike (+188.2%).

## Positive Signals
No positive anomaly signals detected in this period.

## Recommended Actions
- Review daily budget allocation for '{first_camp}'.
"""

    mock_llm = MagicMock()
    mock_llm.generate_briefing.return_value = ExecutiveBriefing(
        summary="Evaluation identified 5 critical performance anomalies.",
        raw_markdown=mock_markdown,
        critical_findings=[f"Campaign '{first_camp}' experienced a CPA spike (+188.2%)."],
        recommended_actions=[f"Review daily budget allocation for '{first_camp}'."],
    )

    output_file = tmp_path / "sample_briefing.md"
    use_case = GenerateBriefingUseCase(llm_service=mock_llm, output_dir=tmp_path)

    result = use_case.execute(anomalies, save_path=output_file)

    assert isinstance(result, ExecutiveBriefing)
    assert output_file.is_file()
    saved_content = output_file.read_text(encoding="utf-8")
    assert "# Executive Briefing" in saved_content
    assert first_camp in saved_content


def test_generate_briefing_use_case_fallback_on_llm_failure(tmp_path: Path) -> None:
    """Verify GenerateBriefingUseCase gracefully falls back when LLM service fails."""
    anomalies = load_sample_anomalies()

    failing_llm = MagicMock()
    failing_llm.generate_briefing.side_effect = LLMServiceError("OpenAI Rate Limit Exceeded")

    output_file = tmp_path / "sample_briefing_fallback.md"
    use_case = GenerateBriefingUseCase(llm_service=failing_llm, output_dir=tmp_path)

    result = use_case.execute(anomalies, save_path=output_file)

    assert isinstance(result, ExecutiveBriefing)
    assert output_file.is_file()
    saved_content = output_file.read_text(encoding="utf-8")
    assert "Executive Briefing (Deterministic Fallback)" in saved_content
    assert anomalies[0].campaign_name in saved_content


def test_generate_briefing_empty_anomalies_fallback(tmp_path: Path) -> None:
    """Verify fallback generation when anomalies list is empty."""
    failing_llm = MagicMock()
    failing_llm.generate_briefing.side_effect = LLMServiceError("No input data")

    use_case = GenerateBriefingUseCase(llm_service=failing_llm, output_dir=tmp_path)
    result = use_case.execute([], save_path=tmp_path / "empty.md")

    assert "No performance anomalies were detected" in result.summary
    assert "No performance anomalies were detected" in result.raw_markdown


def test_generate_briefing_with_validation_warning(tmp_path: Path) -> None:
    """Verify GenerateBriefingUseCase attaches warning banner when LLM output has discrepancy."""
    anomalies = load_sample_anomalies()
    discrepant_markdown = "# Executive Briefing\n- Campaign 'Fake_Camp_1' CPA spiked."

    mock_llm = MagicMock()
    mock_llm.generate_briefing.return_value = ExecutiveBriefing(
        summary="Summary",
        raw_markdown=discrepant_markdown,
    )

    use_case = GenerateBriefingUseCase(llm_service=mock_llm, output_dir=tmp_path)
    result = use_case.execute(anomalies, save_path=tmp_path / "warn.md")

    assert "WARNING: DATA DISCREPANCY DETECTED IN BRIEFING" in result.raw_markdown
    assert "Fake_Camp_1" in result.raw_markdown
