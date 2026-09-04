from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from src.infrastructure.config.settings import Settings, get_settings


def test_settings_default_values() -> None:
    """Verify that Settings instantiates with expected default values."""
    settings = Settings()

    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.port == 8000
    assert settings.reporting_currency == "USD"
    assert settings.anomaly_baseline_days == 14
    assert settings.anomaly_zscore_threshold == 2.0
    assert settings.openai_model == "gpt-4o-mini"


def test_settings_base_dir_resolution() -> None:
    """Verify that base_dir accurately points to the project root directory."""
    settings = Settings()
    base_dir = settings.base_dir

    assert isinstance(base_dir, Path)
    assert base_dir.exists()
    assert (base_dir / "pyproject.toml").exists()
    assert (base_dir / "src").exists()


def test_settings_relative_directory_resolution() -> None:
    """Verify that relative directory names resolve to absolute paths under base_dir."""
    settings = Settings(
        data_dir_name="data",
        output_dir_name="output",
        prompts_dir_name="prompts",
    )

    assert settings.data_dir == settings.base_dir / "data"
    assert settings.output_dir == settings.base_dir / "output"
    assert settings.prompts_dir == settings.base_dir / "prompts"


def test_settings_absolute_directory_resolution(tmp_path: Path) -> None:
    """Verify that absolute directory paths are resolved directly without prepending base_dir."""
    custom_data = tmp_path / "custom_data"
    custom_output = tmp_path / "custom_output"
    custom_prompts = tmp_path / "custom_prompts"

    settings = Settings(
        data_dir_name=str(custom_data),
        output_dir_name=str(custom_output),
        prompts_dir_name=str(custom_prompts),
    )

    assert settings.data_dir == custom_data
    assert settings.output_dir == custom_output
    assert settings.prompts_dir == custom_prompts


def test_settings_env_var_override(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Verify that environment variables override configuration defaults."""
    custom_data = tmp_path / "env_data"
    monkeypatch.setenv("DATA_DIR", str(custom_data))
    monkeypatch.setenv("ANOMALY_BASELINE_DAYS", "21")
    monkeypatch.setenv("REPORTING_CURRENCY", "EUR")

    settings = Settings()

    assert settings.data_dir == custom_data
    assert settings.anomaly_baseline_days == 21
    assert settings.reporting_currency == "EUR"


def test_settings_custom_overrides() -> None:
    """Verify custom instantiation parameters override defaults accurately."""
    settings = Settings(
        environment="production",
        reporting_currency="EUR",
        anomaly_baseline_days=30,
        anomaly_zscore_threshold=3.5,
    )

    assert settings.environment == "production"
    assert settings.reporting_currency == "EUR"
    assert settings.anomaly_baseline_days == 30
    assert settings.anomaly_zscore_threshold == 3.5


def test_get_settings_caching() -> None:
    """Verify get_settings returns a valid Settings instance and caches it."""
    get_settings.cache_clear()
    settings_1 = get_settings()
    settings_2 = get_settings()

    assert isinstance(settings_1, Settings)
    assert settings_1 is settings_2
