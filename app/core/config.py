
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ProviderMode = Literal["json", "api"]


class Settings(BaseSettings):
    """Central configuration for the VPM360 simulator."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "VPM360 Simulator"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # PostgreSQL
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://appuser:replace_me@localhost:5432/vpm_simulator"
    )
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    db_pool_timeout: int = Field(default=30, ge=1)

    # Integration providers
    tenable_provider: ProviderMode = "json"
    cmdb_provider: ProviderMode = "json"
    itsm_provider: ProviderMode = "json"
    satellite_provider: ProviderMode = "json"

    # Fixtures and HTTP clients
    fixture_dir: str = "fixtures"
    api_timeout_seconds: float = Field(default=30, gt=0)
    api_max_retries: int = Field(default=3, ge=0, le=10)

    # Tenable
    tenable_base_url: str = ""
    tenable_access_key: SecretStr | None = None
    tenable_secret_key: SecretStr | None = None
    tenable_verify_tls: bool = True

    # BMC Helix CMDB
    cmdb_base_url: str = ""
    cmdb_username: str = ""
    cmdb_password: SecretStr | None = None
    cmdb_verify_tls: bool = True

    # BMC Helix ITSM
    itsm_base_url: str = ""
    itsm_username: str = ""
    itsm_password: SecretStr | None = None
    itsm_verify_tls: bool = True

    # Red Hat Satellite
    satellite_base_url: str = ""
    satellite_username: str = ""
    satellite_password: SecretStr | None = None
    satellite_verify_tls: bool = True

    @field_validator(
        "app_env",
        "log_level",
        mode="before",
    )
    @classmethod
    def normalize_text_settings(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator(
        "tenable_base_url",
        "cmdb_base_url",
        "itsm_base_url",
        "satellite_base_url",
    )
    @classmethod
    def normalize_base_urls(cls, value: str) -> str:
        return value.strip().rstrip("/")

    def provider_for(self, integration: str) -> ProviderMode:
        """Return the configured provider for an integration."""
        providers: dict[str, ProviderMode] = {
            "tenable": self.tenable_provider,
            "cmdb": self.cmdb_provider,
            "itsm": self.itsm_provider,
            "satellite": self.satellite_provider,
        }

        key = integration.strip().lower()

        if key not in providers:
            raise ValueError(
                f"Unknown integration: {integration!r}. "
                f"Supported integrations: {', '.join(providers)}"
            )

        return providers[key]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Create settings once and reuse them throughout the application."""
    return Settings()
