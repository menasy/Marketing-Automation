"""Unit tests validating Senior Marketing Lead prompt directive structure and integration."""

from unittest.mock import MagicMock

from src.agent.runtime.gemini_client import IStructuredLLMClient
from src.agent.runtime.orchestrator import BatchReasoningOrchestrator
from src.infrastructure.config.settings import get_settings
from src.infrastructure.llm.prompt_loader import PromptLoader


def test_executive_briefing_prompt_exists_and_non_empty() -> None:
    """Verify prompts/executive_briefing.md exists on disk and is non-empty."""
    settings = get_settings()
    prompt_path = settings.prompts_dir / "executive_briefing.md"

    assert prompt_path.is_file(), f"Prompt file does not exist at {prompt_path}"
    content = prompt_path.read_text(encoding="utf-8").strip()
    assert len(content) > 100, "Prompt file content is unexpectedly short or empty"


def test_executive_briefing_contains_required_sections_and_tokens() -> None:
    """Verify prompt directive contains mandatory personas, rules, tokens, and constraints."""
    settings = get_settings()
    prompt_path = settings.prompts_dir / "executive_briefing.md"
    content = prompt_path.read_text(encoding="utf-8")

    # Persona & Mission
    assert "Senior Growth & Performance Marketing Director" in content
    assert "Senior Performance Marketing Lead" in content
    assert "EvidenceDossier" in content

    # Issue Types & Classification
    assert "DATA_QUALITY" in content
    assert "PERFORMANCE" in content

    # Funnel Correlation Principles
    assert "Tracking / Pixel / Attribution Failure Pattern" in content
    assert "Creative Fatigue / Audience Saturation Pattern" in content
    assert "Auction Competition / Bid Pressure Pattern" in content
    assert "Landing Page / Conversion Funnel Failure Pattern" in content

    # Hypothesis Formulation & Grounding
    assert "Hypothesis" in content
    assert "competing_hypotheses" in content
    assert "selected_hypothesis" in content
    assert "missing_evidence" in content

    # Operational Action Matrix
    assert "budget_action" in content
    assert "bid_action" in content
    assert "creative_action" in content
    assert "tracking_action" in content

    # Turkish Output & Language Rules
    assert "Turkish" in content
    assert "executive_summary" in content

    # Schema Contract Enforcement
    assert "BatchAnalysisResult" in content

    # Placeholder compatibility
    assert "{{anomalies_json}}" in content


def test_orchestrator_loads_and_validates_rewritten_prompt() -> None:
    """Verify BatchReasoningOrchestrator successfully loads the system instruction template."""
    mock_client = MagicMock(spec=IStructuredLLMClient)
    settings = get_settings()
    prompt_path = settings.prompts_dir / "executive_briefing.md"

    orchestrator = BatchReasoningOrchestrator(
        client=mock_client,
        prompt_template_path=prompt_path,
    )

    system_instruction = orchestrator.load_system_instruction()
    assert system_instruction is not None
    assert "Senior Growth & Performance Marketing Director" in system_instruction
    assert "BatchAnalysisResult" in system_instruction


def test_prompt_loader_renders_rewritten_prompt() -> None:
    """Verify PromptLoader successfully renders prompt with anomalies payload."""
    settings = get_settings()
    prompt_path = settings.prompts_dir / "executive_briefing.md"

    loader = PromptLoader(prompt_path=prompt_path)
    raw_template = loader.load_raw_template()
    assert len(raw_template) > 0

    rendered = loader.render_prompt(anomalies=[{"campaign": "Test_Campaign", "spend": 100.0}])
    assert "Senior Growth & Performance Marketing Director" in rendered
    assert "Test_Campaign" in rendered
    assert "{{anomalies_json}}" not in rendered
