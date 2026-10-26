"""Central configuration for the VPM360 simulator."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ProviderMode = Literal["json", "api"]
HttpMethod = Literal["GET", "POST"]
TenablePagingMode = Literal["none", "offset_limit"]
TenableRequestLocation = Literal["query", "json"]


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

    # Paths supplied in the BRD.
    tenable_scan_result_path: str = "/rest/scanResult"
    tenable_analysis_path: str = "/rest/analysis"

    # The BRD supplies a fields query for scanResult. Its actual behavior
    # must be validated against the installed client API.
    tenable_scan_result_fields: str = (
        "id,name,description,status,details,resultType,startTime,"
        "finishtime,scanduration,repository"
    )

    # Client contract settings. None/blank means the API provider must
    # not activate because the contract has not been confirmed.
    tenable_auth_header_name: str = ""
    tenable_auth_header_prefix: str = ""

    tenable_scan_result_method: HttpMethod | None = None
    tenable_analysis_method: HttpMethod | None = None

    tenable_analysis_id_param: str = ""
    tenable_analysis_id_location: TenableRequestLocation | None = None

    # Set to "none" only after confirming that scanResult returns the
    # complete result set. Otherwise configure the approved paging contract.
    tenable_scan_result_paging_mode: TenablePagingMode | None = None
    tenable_scan_result_offset_param: str = ""
    tenable_scan_result_limit_param: str = ""
    tenable_scan_result_page_size: int = Field(default=100, ge=1, le=1000)
    tenable_max_scan_results: int = Field(default=10000, ge=1)

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

    @field_validator("app_env", "log_level", mode="before")
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

    @field_validator(
        "tenable_scan_result_path",
        "tenable_analysis_path",
    )
    @classmethod
    def validate_tenable_path(cls, value: str) -> str:
        value = value.strip()

        if not value.startswith("/") or value.startswith("//"):
            raise ValueError("Tenable endpoint paths must start with '/'")

        return value

    def provider_for(self, integration: str) -> ProviderMode:
        """Return the configured provider for the selected integration."""
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