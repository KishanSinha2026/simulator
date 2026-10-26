"""Pydantic schemas for Tenable vulnerability findings."""

from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class TenableFindingBase(BaseModel):
    """Common fields for a Tenable vulnerability finding."""

    model_config = ConfigDict(extra="forbid")

    source_finding_id: str | None = Field(
        default=None,
        max_length=150,
    )
    scan_id: int | None = None

    plugin_id: int | None = Field(default=None, gt=0)
    plugin_name: str | None = Field(
        default=None,
        max_length=500,
    )

    ip_address: str | None = Field(default=None, max_length=45)
    dns_name: str | None = Field(default=None, max_length=255)
    host_id: str | None = Field(default=None, max_length=150)

    severity: str | None = Field(default=None, max_length=50)
    synopsis: str | None = None
    description: str | None = None
    plugin_output: str | None = None
    steps_to_remediate: str | None = None

    cvss_v3_base_score: float | None = Field(
        default=None,
        ge=0,
        le=10,
    )
    cvss_v4_base_score: float | None = Field(
        default=None,
        ge=0,
        le=10,
    )

    first_discovered: datetime | None = None
    last_observed: datetime | None = None

    repository: str | None = Field(default=None, max_length=255)
    protocol: str | None = Field(default=None, max_length=30)
    port: int | None = Field(default=None, ge=0, le=65535)

    source_payload: dict[str, Any] | None = Field(
        default_factory=dict,
    )


class TenableFindingCreate(TenableFindingBase):
    """Schema for creating a simulated Tenable finding."""

    plugin_id: int = Field(gt=0)
    plugin_name: str = Field(min_length=1, max_length=500)

    # The service will persist these in tenable_finding_cves,
    # rather than passing this field directly to TenableFinding.
    cve_ids: list[str] = Field(default_factory=list)

    @field_validator("plugin_name")
    @classmethod
    def validate_plugin_name(cls, value: str) -> str:
        """Reject blank plugin names."""
        value = value.strip()

        if not value:
            raise ValueError("plugin_name cannot be blank")

        return value

    @field_validator("cve_ids")
    @classmethod
    def validate_cve_ids(cls, values: list[str]) -> list[str]:
        """Normalize CVE identifiers and remove duplicates."""
        normalized = []

        for value in values:
            cve = value.strip().upper()

            if not cve:
                raise ValueError("CVE identifiers cannot be blank")

            if cve not in normalized:
                normalized.append(cve)

        return normalized


class TenableFindingCVEResponse(BaseModel):
    """CVE association returned for a Tenable finding."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    finding_id: int
    cve: str


class TenableFindingResponse(TenableFindingBase):
    """Schema returned by the Tenable findings API."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: int
    created_at: datetime
    updated_at: datetime

    cves: list[TenableFindingCVEResponse] = Field(
        default_factory=list,
    )


class TenableFindingListResponse(BaseModel):
    """Paginated list of Tenable findings."""

    model_config = ConfigDict(extra="forbid")

    items: list[TenableFindingResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)
    has_more: bool