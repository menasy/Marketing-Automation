from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly typed application configuration using pydantic-settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    # Application Settings
    environment: Literal["development", "staging", "production", "testing"] = "development"
    log_level: str = "INFO"
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = 8000

    # Reporting Configuration
    reporting_currency: str = "USD"

    # Anomaly Detection Settings
    anomaly_baseline_days: int = Field(default=14, ge=1, le=90)
    anomaly_window_days: int = Field(
        default=14, validation_alias="ANOMALY_WINDOW_DAYS", ge=1, le=90
    )
    anomaly_zscore_threshold: float = Field(default=2.0, gt=0.0)

    # Directory Paths (raw config values)
    data_dir_name: str = Field(default="data", validation_alias="DATA_DIR")
    output_dir_name: str = Field(default="output", validation_alias="OUTPUT_DIR")
    prompts_dir_name: str = Field(default="prompts", validation_alias="PROMPTS_DIR")

    # LLM Settings
    llm_provider: str = Field(default="gemini", validation_alias="LLM_PROVIDER")
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(
        default="gemini-1.5-flash", validation_alias=AliasChoices("GEMINI_MODEL", "LLM_MODEL")
    )
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")

    # Notification Settings
    slack_webhook_url: str = Field(default="", validation_alias="SLACK_WEBHOOK_URL")
    slack_critical_channel: str = Field(
        default="#marketing-alerts-critical", validation_alias="SLACK_CRITICAL_CHANNEL"
    )
    smtp_host: str = Field(default="localhost", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_username: str = Field(default="", validation_alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", validation_alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(
        default="briefing@marketing-automation.local", validation_alias="SMTP_FROM_EMAIL"
    )
    smtp_to_email: str = Field(
        default="executives@marketing-automation.local", validation_alias="SMTP_TO_EMAIL"
    )

    # Integration Settings (Reference)
    google_ads_developer_token: str = Field(default="")
    google_ads_client_id: str = Field(default="")
    google_ads_client_secret: str = Field(default="")

    @property
    def base_dir(self) -> Path:
        """Calculates project root directory based on file location."""
        return Path(__file__).resolve().parent.parent.parent.parent

    @property
    def data_dir(self) -> Path:
        """Resolves absolute path for data directory."""
        path = Path(self.data_dir_name)
        return path if path.is_absolute() else self.base_dir / path

    @property
    def output_dir(self) -> Path:
        """Resolves absolute path for output directory."""
        path = Path(self.output_dir_name)
        return path if path.is_absolute() else self.base_dir / path

    @property
    def prompts_dir(self) -> Path:
        """Resolves absolute path for prompts directory."""
        path = Path(self.prompts_dir_name)
        return path if path.is_absolute() else self.base_dir / path


@lru_cache
def get_settings() -> Settings:
    """Singleton getter for cached application settings."""
    return Settings()
