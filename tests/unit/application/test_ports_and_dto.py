from src.application.dto import PipelineRequest, PipelineResponse
from src.application.ports import (
    IAnomalyDetector,
    IDataReader,
    ILLMService,
    INormalizer,
    INotificationService,
)
from src.domain.enums import MetricDirection, MetricType, Platform, Severity
from src.domain.models import (
    AnomalyItem,
    ExecutiveBriefing,
    NormalizedAdRecord,
)


def test_pipeline_request_dto_serialization() -> None:
    """Verify PipelineRequest DTO default initialization and serialization."""
    req = PipelineRequest()
    assert req.date_from is None
    assert req.date_to is None
    assert req.anomaly_window_days == 14
    assert req.zscore_threshold == 2.0
    assert req.force_refresh is False

    custom_req = PipelineRequest(
        date_from="2026-08-01",
        date_to="2026-08-31",
        anomaly_window_days=30,
        zscore_threshold=3.0,
        force_refresh=True,
    )
    dumped = custom_req.model_dump()
    assert dumped["date_from"] == "2026-08-01"
    assert dumped["anomaly_window_days"] == 30
    assert dumped["force_refresh"] is True


def test_pipeline_response_dto_serialization() -> None:
    """Verify PipelineResponse DTO serialization and deserialization."""
    res = PipelineResponse(
        execution_id="exec-999",
        status="success",
        anomalies_count=2,
        execution_time_seconds=0.85,
        output_paths={"anomalies_json": "/out/anomalies.json"},
    )
    assert res.execution_id == "exec-999"
    assert res.anomalies_count == 2
    assert res.output_paths["anomalies_json"] == "/out/anomalies.json"

    json_str = res.model_dump_json()
    deserialized = PipelineResponse.model_validate_json(json_str)
    assert deserialized.execution_id == res.execution_id
    assert deserialized.anomalies_count == res.anomalies_count


def test_protocol_implementations_type_check() -> None:
    """Verify that dummy implementations satisfy application protocol contracts."""

    class DummyDataReader:
        def read(self, file_path: str) -> list[dict[str, object]]:
            return [{"raw": "data"}]

    class DummyNormalizer:
        def normalize(self, raw_records: list[dict[str, object]]) -> list[NormalizedAdRecord]:
            return [
                NormalizedAdRecord(
                    date="2026-09-01",
                    platform=Platform.GOOGLE_ADS,
                    campaign_name="Test",
                    country="US",
                    currency="USD",
                    spend=10.0,
                    impressions=100,
                    clicks=5,
                    conversions=1.0,
                    conversion_value=20.0,
                )
            ]

    class DummyAnomalyDetector:
        def detect(self, records: list[NormalizedAdRecord], window_days: int) -> list[AnomalyItem]:
            return [
                AnomalyItem(
                    campaign_name="Test",
                    platform=Platform.GOOGLE_ADS,
                    country="US",
                    metric=MetricType.SPEND,
                    current_value=100.0,
                    baseline_value=10.0,
                    change_rate=9.0,
                    z_score=3.0,
                    severity=Severity.CRITICAL,
                    direction=MetricDirection.LOWER_IS_BETTER,
                    detection_method="zscore",
                    rationale="Spend spike",
                )
            ]

    class DummyLLMService:
        def generate_briefing(self, anomalies: list[AnomalyItem]) -> ExecutiveBriefing:
            return ExecutiveBriefing(summary="Summary", raw_markdown="# Briefing")

    class DummyNotificationService:
        def send(self, briefing: ExecutiveBriefing) -> bool:
            return True

    # Type check protocol implementations
    data_reader: IDataReader = DummyDataReader()
    normalizer: INormalizer = DummyNormalizer()
    anomaly_detector: IAnomalyDetector = DummyAnomalyDetector()
    llm_service: ILLMService = DummyLLMService()
    notification_service: INotificationService = DummyNotificationService()

    assert len(data_reader.read("dummy.csv")) == 1
    assert len(normalizer.normalize([])) == 1
    assert len(anomaly_detector.detect([], 14)) == 1
    assert llm_service.generate_briefing([]).summary == "Summary"
    assert notification_service.send(ExecutiveBriefing(summary="S", raw_markdown="M")) is True
