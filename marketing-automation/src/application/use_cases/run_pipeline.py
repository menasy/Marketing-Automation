"""Application use case for orchestrating the complete end-to-end marketing automation pipeline."""

import logging
import time
import uuid
from pathlib import Path

from src.application.dto.pipeline_request import PipelineRequest
from src.application.ports.baseline_provider import IBaselineProvider
from src.application.ports.currency_provider import ICurrencyProvider
from src.application.ports.data_source import IDataReader
from src.application.ports.normalizer import INormalizer
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
from src.infrastructure.reporting.operational_report import OperationalReportWriter

logger = logging.getLogger(__name__)


class RunPipelineUseCase:
    """Pure Application orchestrator executing the 5-stage anomaly detection pipeline.

    Stages:
    1. NormalizeDataUseCase: Ingest, currency convert, and grain aggregate raw ad CSVs.
    2. BuildBaselineUseCase: Historical sliding window splitting and baseline calculation.
    3. DetectAnomaliesUseCase: Rolling Z-score statistical tests & severity classification.
    4. AnalyzeFindingsUseCase: Root-cause analysis, operational ranking, and report rendering.
    5. GenerateBriefingUseCase: LLM executive briefing generation with guardrails.
    """

    def __init__(
        self,
        normalize_data_use_case: NormalizeDataUseCase | None = None,
        build_baseline_use_case: BuildBaselineUseCase | None = None,
        detect_anomalies_use_case: DetectAnomaliesUseCase | None = None,
        analyze_findings_use_case: AnalyzeFindingsUseCase | None = None,
        generate_briefing_use_case: GenerateBriefingUseCase | None = None,
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

        self._google_reader = google_reader or GoogleCSVReader()
        self._google_normalizer = google_normalizer or GoogleNormalizer()
        self._meta_reader = meta_reader or MetaCSVReader()
        self._meta_normalizer = meta_normalizer or MetaNormalizer()

    def execute(self, request: PipelineRequest | None = None) -> PipelineResult:
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
            "Starting pipeline execution [execution_id=%s] [currency=%s] [window_days=%d]",
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
            anomalies_path = Path("output/anomalies.json")
            if anomalies_path.exists():
                output_files["anomalies_json"] = str(anomalies_path)

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
        # Stage 4: Analyze Findings
        # ---------------------------------------------------------------------
        stage_4_name = "analyze_findings"
        stage_4_start = time.perf_counter()
        top_findings: list[OperationalFinding] = []
        try:
            logger.info("Executing Stage 4: Analyze Findings [execution_id=%s]", execution_id)
            top_findings = self._analyze_findings_use_case.execute(anomalies=anomalies)
            findings_path = Path("output/top_3_findings.md")
            if findings_path.exists():
                output_files["top_3_findings_md"] = str(findings_path)

            stage_4_duration = time.perf_counter() - stage_4_start
            stage_statuses[stage_4_name] = "success"
            logger.info(
                "Stage complete [execution_id=%s] [stage=%s] [status=%s] [duration=%.4fs]",
                execution_id,
                stage_4_name,
                "success",
                stage_4_duration,
            )
        except Exception as err:
            stage_4_duration = time.perf_counter() - stage_4_start
            stage_statuses[stage_4_name] = "failed"
            total_duration = time.perf_counter() - overall_start_time
            logger.error(
                "Stage failed [execution_id=%s] [stage=%s] [duration=%.4fs] [error=%s]",
                execution_id,
                stage_4_name,
                stage_4_duration,
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
        # Stage 5: Generate Briefing (Non-critical Stage with Graceful Fallback)
        # ---------------------------------------------------------------------
        stage_5_name = "generate_briefing"
        stage_5_start = time.perf_counter()
        pipeline_status = "success"
        briefing_summary = ""
        recommended_actions: list[str] = []
        try:
            logger.info("Executing Stage 5: Generate Briefing [execution_id=%s]", execution_id)
            briefing = self._generate_briefing_use_case.execute(anomalies=anomalies)
            if briefing:
                briefing_summary = briefing.summary
                recommended_actions = briefing.recommended_actions

            briefing_path = Path("output/sample_briefing.md")
            if briefing_path.exists():
                output_files["sample_briefing_md"] = str(briefing_path)

            stage_5_duration = time.perf_counter() - stage_5_start
            stage_statuses[stage_5_name] = "success"
            logger.info(
                "Stage complete [execution_id=%s] [stage=%s] [status=%s] [duration=%.4fs]",
                execution_id,
                stage_5_name,
                "success",
                stage_5_duration,
            )
        except Exception as err:
            stage_5_duration = time.perf_counter() - stage_5_start
            stage_statuses[stage_5_name] = "fallback"
            pipeline_status = "partial_success"
            logger.warning(
                "Non-critical stage fallback [execution_id=%s] [duration=%.4fs] [error=%s]",
                execution_id,
                stage_5_duration,
                str(err),
            )

        # ---------------------------------------------------------------------
        # Result Computation & Summary
        # ---------------------------------------------------------------------
        total_duration = time.perf_counter() - overall_start_time
        critical_count = sum(
            1
            for a in anomalies
            if (a.severity.value if hasattr(a.severity, "value") else str(a.severity)).lower()
            in (Severity.CRITICAL.value, Severity.HIGH.value, "critical", "high")
        )

        # Serialize top findings using DRY helper from OperationalReportWriter
        top_3_findings_dicts: list[dict[str, str]] = [
            OperationalReportWriter.to_finding_dict(f) for f in top_findings
        ]

        # Derive top_anomalies from actual findings instead of raw anomaly dump
        top_anomalies: list[str] = []
        for f in top_findings:
            plat = f.platform.value if hasattr(f.platform, "value") else str(f.platform)
            top_anomalies.append(
                f"- *{f.campaign_name}* ({plat}/{f.country}): {f.metric_change}"
            )

        # Derive recommended_actions from findings if LLM didn't produce them
        if not recommended_actions:
            recommended_actions = [f.operational_action for f in top_findings]
        if not recommended_actions:
            recommended_actions = [
                "Anomali tespit edilmedi veya aksiyon gerektiren bulgu yok.",
            ]

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

