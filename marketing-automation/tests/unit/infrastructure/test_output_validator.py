import pytest

from src.domain.enums import MetricDirection, MetricType, Platform, Severity
from src.domain.exceptions import LLMValidationError
from src.domain.models import AnomalyItem
from src.infrastructure.llm.output_validator import OutputValidator


@pytest.fixture
def sample_anomalies() -> list[AnomalyItem]:
    """Fixture providing sample valid AnomalyItem objects."""
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
        ),
        AnomalyItem(
            campaign_name="AH | Shopping | UK",
            platform=Platform.GOOGLE_ADS,
            country="UK",
            metric=MetricType.ROAS,
            current_value=2.88,
            baseline_value=7.96,
            change_rate=-0.638,
            z_score=-4.46,
            severity=Severity.CRITICAL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            detection_method="rolling_zscore",
            rationale="ROAS dropped by -63.8%",
        ),
    ]


def test_output_validator_valid_briefing(sample_anomalies: list[AnomalyItem]) -> None:
    """Verify that a valid briefing grounded in input data passes validation."""
    validator = OutputValidator()
    valid_markdown = """# Executive Briefing

## Executive Summary
2 critical anomalies were detected across Google Ads campaigns in UK.

## Critical Anomalies
- Campaign 'AH | Search | Generic' CPA spiked (+188.2%, current: 81.67, base: 28.34, z: 8.46).
- Campaign 'AH | Shopping | UK' ROAS dropped by -63.8% (current: 2.88, baseline: 7.96).



## Positive Signals
No positive anomaly signals detected in this period.

## Recommended Actions
- Audit daily budgets for 'AH | Search | Generic'.
"""

    is_valid, discrepancies, markdown_out = validator.validate(
        valid_markdown, sample_anomalies, strict=True
    )
    assert is_valid is True
    assert len(discrepancies) == 0
    assert markdown_out == valid_markdown


def test_output_validator_hallucinated_campaign(sample_anomalies: list[AnomalyItem]) -> None:
    """Verify that hallucinated campaign names trigger validation error in strict mode."""
    validator = OutputValidator()
    hallucinated_markdown = """# Executive Briefing

## Critical Anomalies
- Campaign 'Fake_Nonexistent_Campaign_X' CPA spiked by +188.2%.
"""

    with pytest.raises(LLMValidationError, match="Hallucinated or unverified campaign name"):
        validator.validate(hallucinated_markdown, sample_anomalies, strict=True)

    # Non-strict mode prepends warning banner
    is_valid, discrepancies, markdown_out = validator.validate(
        hallucinated_markdown, sample_anomalies, strict=False
    )
    assert is_valid is False
    assert len(discrepancies) >= 1
    assert "WARNING: DATA DISCREPANCY DETECTED IN BRIEFING" in markdown_out
    assert "Fake_Nonexistent_Campaign_X" in markdown_out


def test_output_validator_hallucinated_numeric(sample_anomalies: list[AnomalyItem]) -> None:
    """Verify that hallucinated percentage values trigger validation error."""
    validator = OutputValidator()
    fake_numeric_markdown = """# Executive Briefing

## Critical Anomalies
- Campaign 'AH | Search | Generic' CPA spiked by +999.9%.
"""

    with pytest.raises(LLMValidationError, match="Unverified or hallucinated percentage figure"):
        validator.validate(fake_numeric_markdown, sample_anomalies, strict=True)


def test_output_validator_empty_anomalies() -> None:
    """Verify validator handles empty anomalies payload gracefully."""
    validator = OutputValidator()
    empty_markdown = "# Executive Briefing\nNo anomalies detected."

    is_valid, discrepancies, markdown_out = validator.validate(empty_markdown, [], strict=True)
    assert is_valid is True
    assert len(discrepancies) == 0
    assert markdown_out == empty_markdown
