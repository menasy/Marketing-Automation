"""Dependency injection container for FastAPI presentation layer."""

from functools import lru_cache

from src.application.use_cases.run_pipeline import RunPipelineUseCase
from src.infrastructure.config.settings import Settings, get_settings


@lru_cache
def get_app_settings() -> Settings:
    """Provides application configuration singleton for API dependency injection."""
    return get_settings()


def get_run_pipeline_use_case() -> RunPipelineUseCase:
    """Provides an instance of RunPipelineUseCase for API dependency injection."""
    return RunPipelineUseCase()
