from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Immutable domain entity representing the output summary of a pipeline execution."""

    execution_id: str
    status: str
    anomalies_count: int
    critical_count: int = 0
    duration_seconds: float = 0.0
    output_files: dict[str, str] = field(default_factory=dict)
    briefing_summary: str = ""
    top_anomalies: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    top_3_findings: list[dict[str, str]] = field(default_factory=list)
    stage_statuses: dict[str, str] = field(default_factory=dict)
    execution_time_seconds: float = 0.0
    output_paths: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Synchronize field aliases for backwards compatibility and strict typed API."""
        if self.duration_seconds == 0.0 and self.execution_time_seconds != 0.0:
            object.__setattr__(self, "duration_seconds", self.execution_time_seconds)
        elif self.execution_time_seconds == 0.0 and self.duration_seconds != 0.0:
            object.__setattr__(self, "execution_time_seconds", self.duration_seconds)

        if not self.output_files and self.output_paths:
            object.__setattr__(self, "output_files", self.output_paths)
        elif not self.output_paths and self.output_files:
            object.__setattr__(self, "output_paths", self.output_files)
