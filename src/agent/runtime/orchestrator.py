"""Single-turn batch reasoning orchestrator executing Gemini analysis over EvidenceDossiers."""

import json
import logging
from pathlib import Path

from src.agent.exceptions import AgentExecutionError
from src.agent.guardrails.fallback import DeterministicFallbackGenerator
from src.agent.guardrails.verifier import OutputVerifier
from src.agent.runtime.context import AgentContext
from src.agent.runtime.gemini_client import IStructuredLLMClient
from src.agent.schemas.reasoning import BatchAnalysisResult
from src.domain.models.evidence_dossier import EvidenceDossier
from src.infrastructure.config.settings import get_settings

logger = logging.getLogger(__name__)


class BatchReasoningOrchestrator:
    """Orchestrates single-turn batch LLM reasoning by serializing evidence dossiers."""

    def __init__(
        self,
        client: IStructuredLLMClient,
        prompt_template_path: Path | str | None = None,
        verifier: OutputVerifier | None = None,
        fallback_generator: DeterministicFallbackGenerator | None = None,
    ) -> None:
        """Initialize orchestrator with client, prompt path, verifier, and fallback."""
        self._client = client
        if prompt_template_path is None:
            settings = get_settings()
            self._prompt_template_path = settings.prompts_dir / "executive_briefing.md"
        else:
            self._prompt_template_path = Path(prompt_template_path)

        self._verifier = verifier or OutputVerifier()
        self._fallback_generator = fallback_generator or DeterministicFallbackGenerator()

    @property
    def client(self) -> IStructuredLLMClient:
        """Returns injected LLM client."""
        return self._client

    @property
    def prompt_template_path(self) -> Path:
        """Returns system prompt template path."""
        return self._prompt_template_path

    @property
    def verifier(self) -> OutputVerifier:
        """Returns injected OutputVerifier instance."""
        return self._verifier

    @property
    def fallback_generator(self) -> DeterministicFallbackGenerator:
        """Returns injected DeterministicFallbackGenerator instance."""
        return self._fallback_generator

    def serialize_dossier(self, dossier: EvidenceDossier, target_date: str) -> str:
        """Serializes EvidenceDossier into a structured JSON payload for Gemini prompt injection."""
        campaigns_payload: list[dict[str, object]] = []

        for camp in dossier.top_campaign_evidence:
            camp_dict: dict[str, object] = {
                "campaign_id": camp.campaign_id,
                "campaign_name": camp.campaign_name,
                "platform": camp.platform,
                "account_id": camp.account_id,
                "country": camp.country,
                "spend": camp.spend,
                "financial_impact_score": camp.financial_impact_score,
                "metrics": {
                    name: {
                        "metric_name": metric.metric_name,
                        "current_value": metric.current_value,
                        "baseline_value": metric.baseline_value,
                        "delta_pct": metric.delta_pct,
                        "z_score": metric.z_score,
                        "is_anomaly": metric.is_anomaly,
                    }
                    for name, metric in camp.metrics.items()
                },
                "data_quality_signals": [
                    {
                        "signal_type": sig.signal_type.value,
                        "is_triggered": sig.is_triggered,
                        "metric_name": sig.metric_name,
                        "current_value": sig.current_value,
                        "baseline_value": sig.baseline_value,
                        "delta_pct": sig.delta_pct,
                        "factual_statement": sig.factual_statement,
                    }
                    for sig in camp.data_quality_signals
                    if sig.is_triggered
                ],
            }
            campaigns_payload.append(camp_dict)

        payload = {
            "target_date": target_date,
            "baseline_window": dossier.baseline_window,
            "total_anomalies_detected": dossier.total_anomalies_detected,
            "total_campaigns_impacted": dossier.total_campaigns_impacted,
            "top_campaign_evidence": campaigns_payload,
        }

        return json.dumps(payload, indent=2, ensure_ascii=False)

    def load_system_instruction(self) -> str:
        """Reads system prompt template from filesystem.

        Raises:
            AgentExecutionError: If template file does not exist or is empty.
        """
        if not self._prompt_template_path.is_file():
            raise AgentExecutionError(
                f"Prompt template file not found: {self._prompt_template_path}"
            )

        try:
            content = self._prompt_template_path.read_text(encoding="utf-8").strip()
            if not content:
                raise AgentExecutionError(
                    f"Prompt template file is empty: {self._prompt_template_path}"
                )
            return content
        except AgentExecutionError:
            raise
        except Exception as exc:
            raise AgentExecutionError(
                f"Failed to read prompt template file {self._prompt_template_path}: {exc}"
            ) from exc

    def _record_result_hypotheses(self, context: AgentContext, result: BatchAnalysisResult) -> None:
        """Helper to record hypotheses from BatchAnalysisResult into working memory."""
        for finding in result.findings:
            selected_stmt = (
                finding.selected_hypothesis.statement if finding.selected_hypothesis else None
            )
            for hyp in finding.competing_hypotheses:
                is_selected = hyp.statement == selected_stmt
                context.working_memory.record_hypothesis(
                    campaign_name=finding.campaign_name,
                    statement=hyp.statement,
                    selected=is_selected,
                    confidence=hyp.confidence,
                )

    async def run(self, context: AgentContext) -> BatchAnalysisResult:
        """Executes batch reasoning pipeline with self-correction reflection and fail-safe fallback.

        Args:
            context: Session execution context containing EvidenceDossier and execution metadata.

        Returns:
            Structured BatchAnalysisResult instance (either verified LLM result or fallback).
        """
        logger.info(
            "Starting batch reasoning orchestration [execution_id=%s, target_date=%s]",
            context.execution_id,
            context.target_date,
        )

        system_instruction = self.load_system_instruction()
        user_payload = self.serialize_dossier(context.dossier, context.target_date)
        context.working_memory.record_step(
            "PROMPT_SERIALIZATION",
            "Serialized EvidenceDossier for LLM payload",
        )

        try:
            # 1. First Pass Generation
            result = await self._client.generate_structured_analysis(
                system_instruction=system_instruction,
                user_prompt=user_payload,
            )
            logger.info(
                "Gemini API call successful [exec_id=%s]. "
                "Received %d findings. Proceeding to verification.",
                context.execution_id,
                len(result.findings),
            )
            context.working_memory.record_step(
                "INITIAL_GENERATION",
                "Received initial BatchAnalysisResult from LLM",
            )

            # 2. First Pass Verification
            verification = self._verifier.verify(result, context.dossier)
            context.working_memory.record_verification(
                verification.is_valid, verification.errors, verification.warnings
            )
            if verification.is_valid:
                context.result = result
                self._record_result_hypotheses(context, result)
                logger.info(
                    "Batch reasoning passed verification on first attempt [exec_id=%s]",
                    context.execution_id,
                )
                return result

            # 3. Reflection Retry (Attempt 2)
            context.working_memory.record_step(
                "REFLECTION_RETRY",
                "Triggered reflection retry after verification failure",
                errors=list(verification.errors),
            )
            logger.warning(
                "Verification failed on initial attempt [exec_id=%s]. "
                "Errors (%d): %s | Warnings (%d): %s. Triggering reflection retry.",
                context.execution_id,
                len(verification.errors),
                ", ".join(verification.errors),
                len(verification.warnings),
                ", ".join(verification.warnings) if verification.warnings else "none",
            )
            formatted_errors = "\n".join(f"- {err}" for err in verification.errors)
            reflection_user_prompt = (
                "Your previous output failed deterministic verification with errors:\n"
                f"{formatted_errors}\n"
                "Please regenerate the analysis ensuring all cited metrics, numbers, and campaign "
                "names strictly match the EvidenceDossier provided below.\n\n"
                "--- ORIGINAL EVIDENCE DOSSIER ---\n"
                f"{user_payload}"
            )

            retry_result = await self._client.generate_structured_analysis(
                system_instruction=system_instruction,
                user_prompt=reflection_user_prompt,
            )

            retry_verification = self._verifier.verify(retry_result, context.dossier)
            context.working_memory.record_verification(
                retry_verification.is_valid,
                retry_verification.errors,
                retry_verification.warnings,
            )
            if retry_verification.is_valid:
                context.result = retry_result
                self._record_result_hypotheses(context, retry_result)
                logger.info(
                    "Batch reasoning passed verification after reflection retry [exec_id=%s]",
                    context.execution_id,
                )
                return retry_result

            # 4. Fallback Activation on Verification Failure
            logger.error(
                "Verification failed after reflection retry [exec_id=%s]. "
                "Remaining errors (%d): %s. Activating deterministic fallback.",
                context.execution_id,
                len(retry_verification.errors),
                ", ".join(retry_verification.errors),
            )
            context.working_memory.record_step(
                "FALLBACK_ACTIVATION",
                "Activated deterministic fallback generator",
                failure_reasons=list(retry_verification.errors),
            )
            fallback_result = self._fallback_generator.generate(
                context.dossier, retry_verification.errors
            )
            context.result = fallback_result
            return fallback_result

        except Exception as exc:
            logger.error(
                "Gemini API or parsing error [exec_id=%s]. Activating fallback. Error type: %s, "
                "Details: %s",
                context.execution_id,
                type(exc).__name__,
                exc,
            )
            context.working_memory.record_step(
                "FALLBACK_ACTIVATION",
                "Activated deterministic fallback generator",
                failure_reasons=[str(exc)],
            )
            fallback_result = self._fallback_generator.generate(
                context.dossier, (f"LLM API execution error: {exc}",)
            )
            context.result = fallback_result
            return fallback_result
