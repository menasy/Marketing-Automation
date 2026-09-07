"""Application use case for orchestrating the complete end-to-end marketing automation pipeline."""

import logging
import time
import uuid
from datetime import date
from pathlib import Path

from src.agent.runtime.context import AgentContext
from src.agent.runtime.gemini_client import GeminiStructuredClient
from src.agent.runtime.orchestrator import BatchReasoningOrchestrator
from src.agent.schemas.reasoning import BatchAnalysisResult
from src.application.dto.pipeline_request import PipelineRequest
from src.application.ports.baseline_provider import IBaselineProvider
from src.application.ports.currency_provider import ICurrencyProvider
from src.application.ports.data_source import IDataReader
from src.application.ports.normalizer import INormalizer
from src.application.ports.notification import INotificationService
from src.application.use_cases.analyze_findings import AnalyzeFindingsUseCase
from src.application.use_cases.build_baseline import BuildBaselineUseCase
from src.application.use_cases.detect_anomalies import DetectAnomaliesUseCase
from src.application.use_cases.generate_briefing import GenerateBriefingUseCase
from src.application.use_cases.normalize_data import (
    DataSourceConfig,
    NormalizeDataUseCase,
)
from src.domain.enums.severity import Severity
from src.domain.models.anomaly import AnomalyItem
from src.domain.models.operational_finding import OperationalFinding
from src.domain.models.pipeline_result import PipelineResult
from src.domain.services.dossier_compiler import DossierCompiler
from src.infrastructure.anomaly.rolling_baseline import RollingBaselineEngine
from src.infrastructure.data.csv.google_ads_reader import GoogleCSVReader
from src.infrastructure.data.csv.meta_ads_reader import MetaCSVReader
from src.infrastructure.data.normalization.currency_normalizer import (
    StaticCurrencyConverter,
)
from src.infrastructure.data.normalization.google_normalizer import (
    GoogleNormalizer,
)
from src.infrastructure.data.normalization.meta_normalizer import (
    MetaNormalizer,
)
from src.infrastructure.notifications.slack import SlackNotificationService
from src.infrastructure.reporting.artifact_service import ArtifactService
from src.infrastructure.reporting.operational_report import OperationalReportWriter

logger = logging.getLogger(__name__)


class RunPipelineUseCase:
    """Pure Application orchestrator executing the 7-stage agentic anomaly pipeline.

    Stages:
    1. NormalizeDataUseCase: Ingest, currency convert, and aggregate raw ad CSVs.
    2. BuildBaselineUseCase: Historical sliding window splitting and baseline calculation.
    3. DetectAnomaliesUseCase: Rolling Z-score statistical tests & severity classification.
    4. DossierCompiler: Multi-metric EvidenceDossier compilation with DataQualitySignals.
    5. BatchReasoningOrchestrator: Autonomous Gemini reasoning with self-correction & fallback.
    6. ArtifactService: Write output files (anomalies.json, top_3_findings.md, briefing.md).
    7. INotificationService: Dynamic Slack Block Kit notification dispatching.
    """

    def __init__(
        self,
        normalize_data_use_case: NormalizeDataUseCase | None = None,
        build_baseline_use_case: BuildBaselineUseCase | None = None,
        detect_anomalies_use_case: DetectAnomaliesUseCase | None = None,
        analyze_findings_use_case: AnalyzeFindingsUseCase | None = None,
        generate_briefing_use_case: GenerateBriefingUseCase | None = None,
        dossier_compiler: DossierCompiler | None = None,
        batch_orchestrator: BatchReasoningOrchestrator | None = None,
        artifact_service: ArtifactService | None = None,
        notification_service: INotificationService | None = None,
        google_reader: IDataReader | None = None,
        google_normalizer: INormalizer | None = None,
        meta_reader: IDataReader | None = None,
        meta_normalizer: INormalizer | None = None,
        currency_provider: ICurrencyProvider | None = None,
        baseline_provider: IBaselineProvider | None = None,
    ) -> None:
        """Initializes pipeline orchestrator with dependency injection of sub-use cases."""
        self._currency_provider = currency_provider or StaticCurrencyConverter()
        self._normalize_data_use_case = normalize_data_use_case or NormalizeDataUseCase(
            currency_provider=self._currency_provider
        )
        self._build_baseline_use_case = build_baseline_use_case or BuildBaselineUseCase(
            baseline_provider=baseline_provider or RollingBaselineEngine()
        )
        self._detect_anomalies_use_case = detect_anomalies_use_case or DetectAnomaliesUseCase()
        self._analyze_findings_use_case = analyze_findings_use_case or AnalyzeFindingsUseCase()
        self._generate_briefing_use_case = generate_briefing_use_case or GenerateBriefingUseCase()

        self._dossier_compiler = dossier_compiler or DossierCompiler()
        self._batch_orchestrator = batch_orchestrator or BatchReasoningOrchestrator(
            client=GeminiStructuredClient()
        )
        self._artifact_service = artifact_service or ArtifactService()
        self._notification_service = notification_service or SlackNotificationService()

        self._google_reader = google_reader or GoogleCSVReader()
        self._google_normalizer = google_normalizer or GoogleNormalizer()
        self._meta_reader = meta_reader or MetaCSVReader()
        self._meta_normalizer = meta_normalizer or MetaNormalizer()

    async def execute(self, request: PipelineRequest | None = None) -> PipelineResult:
        """Executes the full pipeline workflow sequentially with observability and fault tolerance.

        Args:
            request: Optional PipelineRequest DTO containing run parameters.

        Returns:
            Structured PipelineResult entity summarizing stage execution statuses and metrics.
        """
        pipeline_request = request if request is not None else PipelineRequest()
        execution_id = str(uuid.uuid4())
        overall_start_time = time.perf_counter()

        logger.info(
            "Starting agentic pipeline execution [execution_id=%s] [currency=%s] [window_days=%d]",
            execution_id,
            pipeline_request.reporting_currency,
            pipeline_request.window_days,
        )

        stage_statuses: dict[str, str] = {}
        output_files: dict[str, str] = {}
        anomalies: list[AnomalyItem] = []

        # ---------------------------------------------------------------------
        # Stage 1: Data Normalization
        # ---------------------------------------------------------------------
        stage_1_name = "normalize_data"
        stage_1_start = time.perf_counter()
        records = []
        try:
            logger.info("Executing Stage 1: Data Normalization [execution_id=%s]", execution_id)
            sources: list[DataSourceConfig] = []

            if pipeline_request.data_dir:
                data_path = Path(pipeline_request.data_dir)
                google_path = str(data_path / "google_ads_daily.csv")
                meta_path = str(data_path / "meta_ads_daily.csv")
            else:
                google_path = pipeline_request.google_csv_path or "data/google_ads_daily.csv"
                meta_path = pipeline_request.meta_csv_path or "data/meta_ads_daily.csv"

            if pipeline_request.google_csv_path or Path(google_path).exists():
                sources.append(
                    DataSourceConfig(
                        file_path=google_path,
                        reader=self._google_reader,
                        normalizer=self._google_normalizer,
                    )
                )

            if pipeline_request.meta_csv_path or Path(meta_path).exists():
                sources.append(
                    DataSourceConfig(
                        file_path=meta_path,
                        reader=self._meta_reader,
                        normalizer=self._meta_normalizer,
                    )
                )

            if sources:
                norm_result = self._normalize_data_use_case.execute(sources)
                records = norm_result.records

            stage_1_duration = time.perf_counter() - stage_1_start
            stage_statuses[stage_1_name] = "success"
            logger.info(
                "Stage complete [execution_id=%s] [stage=%s] [status=%s] [duration=%.4fs]",
                execution_id,
                stage_1_name,
                "success",
                stage_1_duration,
            )
        except Exception as err:
            stage_1_duration = time.perf_counter() - stage_1_start
            stage_statuses[stage_1_name] = "failed"
            total_duration = time.perf_counter() - overall_start_time
            logger.error(
                "Stage failed [execution_id=%s] [stage=%s] [duration=%.4fs] [error=%s]",
                execution_id,
                stage_1_name,
                stage_1_duration,
                str(err),
            )
            return PipelineResult(
                execution_id=execution_id,
                status="failed",
                anomalies_count=0,
                critical_count=0,
                duration_seconds=total_duration,
                output_files=output_files,
                stage_statuses=stage_statuses,
            )

        # ---------------------------------------------------------------------
        # Stage 2: Build Baseline
        # ---------------------------------------------------------------------
        stage_2_name = "build_baseline"
        stage_2_start = time.perf_counter()
        try:
            logger.info("Executing Stage 2: Build Baseline [execution_id=%s]", execution_id)
            if records:
                self._build_baseline_use_case.execute(
                    records=records,
                    target_date=pipeline_request.target_date,
                    window_days=pipeline_request.window_days,
                )

            stage_2_duration = time.perf_counter() - stage_2_start
            stage_statuses[stage_2_name] = "success"
            logger.info(
                "Stage complete [execution_id=%s] [stage=%s] [status=%s] [duration=%.4fs]",
                execution_id,
                stage_2_name,
                "success",
                stage_2_duration,
            )
        except Exception as err:
            stage_2_duration = time.perf_counter() - stage_2_start
            stage_statuses[stage_2_name] = "failed"
            total_duration = time.perf_counter() - overall_start_time
            logger.error(
                "Stage failed [execution_id=%s] [stage=%s] [duration=%.4fs] [error=%s]",
                execution_id,
                stage_2_name,
                stage_2_duration,
                str(err),
            )
            return PipelineResult(
                execution_id=execution_id,
                status="failed",
                anomalies_count=0,
                critical_count=0,
                duration_seconds=total_duration,
                output_files=output_files,
                stage_statuses=stage_statuses,
            )

        # ---------------------------------------------------------------------
        # Stage 3: Detect Anomalies
        # ---------------------------------------------------------------------
        stage_3_name = "detect_anomalies"
        stage_3_start = time.perf_counter()
        try:
            logger.info("Executing Stage 3: Detect Anomalies [execution_id=%s]", execution_id)
            anomalies = self._detect_anomalies_use_case.detect(
                records=records, window_days=pipeline_request.window_days
            )

            stage_3_duration = time.perf_counter() - stage_3_start
            stage_statuses[stage_3_name] = "success"
            logger.info(
                "Stage complete [execution_id=%s] [stage=%s] [status=%s] [duration=%.4fs]",
                execution_id,
                stage_3_name,
                "success",
                stage_3_duration,
            )
        except Exception as err:
            stage_3_duration = time.perf_counter() - stage_3_start
            stage_statuses[stage_3_name] = "failed"
            total_duration = time.perf_counter() - overall_start_time
            logger.error(
                "Stage failed [execution_id=%s] [stage=%s] [duration=%.4fs] [error=%s]",
                execution_id,
                stage_3_name,
                stage_3_duration,
                str(err),
            )
            return PipelineResult(
                execution_id=execution_id,
                status="failed",
                anomalies_count=0,
                critical_count=0,
                duration_seconds=total_duration,
                output_files=output_files,
                stage_statuses=stage_statuses,
            )

        # ---------------------------------------------------------------------
        # Stage 4: Compile Evidence Dossier
        # ---------------------------------------------------------------------
        stage_4_name = "compile_dossier"
        stage_4_start = time.perf_counter()
        if pipeline_request.target_date:
            if isinstance(pipeline_request.target_date, date):
                target_date_str = pipeline_request.target_date.isoformat()
            else:
                target_date_str = str(pipeline_request.target_date)
        elif records:
            max_rec_date = max(r.date for r in records)
            target_date_str = (
                max_rec_date.isoformat() if isinstance(max_rec_date, date) else str(max_rec_date)
            )
        else:
            target_date_str = date.today().isoformat()

        baseline_window_str = (
            f"{pipeline_request.window_days}-day rolling window ending {target_date_str}"
        )

        try:
            logger.info(
                "Executing Stage 4: Compile Evidence Dossier [execution_id=%s]", execution_id
            )
            dossier = self._dossier_compiler.compile_dossier(
                anomalies=anomalies,
                records=records,
                target_date=target_date_str,
                baseline_window=baseline_window_str,
            )
            stage_4_duration = time.perf_counter() - stage_4_start
            stage_statuses[stage_4_name] = "success"
            logger.info(
                "Stage complete [execution_id=%s] [stage=%s] [duration=%.4fs]",
                execution_id,
                stage_4_name,
                stage_4_duration,
            )
        except Exception as err:
            stage_statuses[stage_4_name] = "failed"
            total_duration = time.perf_counter() - overall_start_time
            logger.error(
                "Stage failed [execution_id=%s] [stage=%s] [error=%s]",
                execution_id,
                stage_4_name,
                str(err),
            )
            return PipelineResult(
                execution_id=execution_id,
                status="failed",
                anomalies_count=len(anomalies),
                critical_count=0,
                duration_seconds=total_duration,
                output_files=output_files,
                stage_statuses=stage_statuses,
            )

        # ---------------------------------------------------------------------
        # Stage 5: Execute Batch Reasoning Orchestrator
        # ---------------------------------------------------------------------
        stage_5_name = "agent_reasoning"
        stage_5_start = time.perf_counter()
        pipeline_status = "success"
        batch_result: BatchAnalysisResult | None = None
        try:
            logger.info(
                "Executing Stage 5: Agent Reasoning Orchestrator [execution_id=%s]", execution_id
            )
            context = AgentContext(
                execution_id=execution_id,
                target_date=target_date_str,
                dossier=dossier,
            )
            batch_result = await self._batch_orchestrator.run(context)
            stage_5_duration = time.perf_counter() - stage_5_start
            stage_statuses[stage_5_name] = "success"
            logger.info(
                "Stage complete [execution_id=%s] [stage=%s] [duration=%.4fs]",
                execution_id,
                stage_5_name,
                stage_5_duration,
            )
        except Exception as err:
            stage_statuses[stage_5_name] = "fallback"

            pipeline_status = "partial_success"
            logger.warning(
                "Stage fallback [execution_id=%s] [stage=%s] [error=%s]",
                execution_id,
                stage_5_name,
                str(err),
            )

        # ---------------------------------------------------------------------
        # Stage 6: Write Artifacts via ArtifactService
        # ---------------------------------------------------------------------
        stage_6_name = "write_artifacts"
        stage_6_start = time.perf_counter()
        out_dir = pipeline_request.output_dir or "output"
        if batch_result is not None:
            try:
                logger.info(
                    "Executing Stage 6: Write Deliverable Artifacts [execution_id=%s]", execution_id
                )
                anom_path, op_path, top_path, brief_path = self._artifact_service.write_all(
                    dossier=dossier,
                    result=batch_result,
                    output_dir=out_dir,
                )
                output_files["anomalies_json"] = str(anom_path)
                output_files["operational_assessment_md"] = str(op_path)
                output_files["top_3_findings_md"] = str(top_path)
                output_files["sample_briefing_md"] = str(brief_path)
                stage_statuses[stage_6_name] = "success"
                logger.info(
                    "Stage complete [execution_id=%s] [stage=%s] [duration=%.4fs]",
                    execution_id,
                    stage_6_name,
                    time.perf_counter() - stage_6_start,
                )
            except Exception as err:
                stage_statuses[stage_6_name] = "fallback"
                pipeline_status = "partial_success"
                logger.warning(
                    "Artifact writing fallback [execution_id=%s] [error=%s]",
                    execution_id,
                    str(err),
                )
        else:
            stage_statuses[stage_6_name] = "skipped"

        # ---------------------------------------------------------------------
        # Stage 7: Dispatch Dynamic Slack Notifications
        # ---------------------------------------------------------------------
        stage_7_name = "dispatch_slack"
        stage_7_start = time.perf_counter()
        try:
            logger.info(
                "Executing Stage 7: Dispatch Slack Notification [execution_id=%s]", execution_id
            )
            if hasattr(self._notification_service, "send_briefing"):
                self._notification_service.send_briefing(dossier=dossier, result=batch_result)
            stage_statuses[stage_7_name] = "success"
            logger.info(
                "Stage complete [execution_id=%s] [stage=%s] [duration=%.4fs]",
                execution_id,
                stage_7_name,
                time.perf_counter() - stage_7_start,
            )
        except Exception as err:
            stage_statuses[stage_7_name] = "fallback"
            logger.warning(
                "Slack dispatch failed gracefully [execution_id=%s] [error=%s]",
                execution_id,
                str(err),
            )

        # ---------------------------------------------------------------------
        # Result Summarization & DTO Population
        # ---------------------------------------------------------------------
        total_duration = time.perf_counter() - overall_start_time
        critical_count = sum(
            1
            for a in anomalies
            if (a.severity.value if hasattr(a.severity, "value") else str(a.severity)).lower()
            in (Severity.CRITICAL.value, Severity.HIGH.value, "critical", "high")
        )

        top_3_findings_dicts: list[dict[str, str]] = []
        top_anomalies: list[str] = []
        recommended_actions: list[str] = []
        briefing_summary = ""

        if batch_result is not None:
            briefing_summary = batch_result.executive_summary
            for finding in batch_result.findings:
                finding_dict = {
                    "campaign_name": finding.campaign_name,
                    "platform": finding.platform,
                    "country": finding.country,
                    "metric_change": finding.metric_change_summary,
                    "issue_type": finding.issue_type,
                    "operational_action": (
                        finding.action_plan.concrete_steps[0]
                        if finding.action_plan.concrete_steps
                        else finding.action_plan.rationale
                    ),
                    "severity": (
                        "CRITICAL"
                        if finding.confidence_score >= 0.8
                        else ("HIGH" if finding.confidence_score >= 0.6 else "MEDIUM")
                    ),
                    "score": str(round(finding.confidence_score * 100, 2)),
                }
                top_3_findings_dicts.append(finding_dict)

                plat = finding.platform
                top_anomalies.append(
                    f"- *{finding.campaign_name}* ({plat}/{finding.country}): "
                    f"{finding.metric_change_summary}"
                )
                act_str = (
                    f"{finding.campaign_name}: {finding.action_plan.budget_action} | "
                    f"{finding.action_plan.creative_action}"
                )
                recommended_actions.append(act_str)

        else:
            top_findings: list[OperationalFinding] = self._analyze_findings_use_case.execute(
                anomalies=anomalies
            )
            top_3_findings_dicts = [
                OperationalReportWriter.to_finding_dict(f) for f in top_findings
            ]
            for f in top_findings:
                plat = f.platform.value if hasattr(f.platform, "value") else str(f.platform)
                top_anomalies.append(
                    f"- *{f.campaign_name}* ({plat}/{f.country}): {f.metric_change}"
                )

        if not recommended_actions:
            recommended_actions = ["Anomali tespit edilmedi veya aksiyon gerektiren bulgu yok."]

        logger.info(
            "Pipeline finished [execution_id=%s] [status=%s] [anomalies=%d] [critical=%d]",
            execution_id,
            pipeline_status,
            len(anomalies),
            critical_count,
        )

        return PipelineResult(
            execution_id=execution_id,
            status=pipeline_status,
            anomalies_count=len(anomalies),
            critical_count=critical_count,
            duration_seconds=total_duration,
            briefing_summary=briefing_summary,
            top_anomalies=top_anomalies,
            recommended_actions=recommended_actions,
            top_3_findings=top_3_findings_dicts,
            output_files=output_files,
            stage_statuses=stage_statuses,
        )
