"""Pydantic schemas for VPM360 Tenable vulnerability findings."""

from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)


class TenableFindingBase(BaseModel):
    """Common fields persisted for a Tenable finding."""

    model_config = ConfigDict(extra="forbid")

    source_finding_id: str | None = Field(
        default=None,
        max_length=150,
    )
    scan_id: int | None = None

    plugin_id: int | None = Field(default=None, gt=0)
    plugin_name: str | None = Field(default=None, max_length=500)

    ip_address: str | None = Field(default=None, max_length=45)
    dns_name: str | None = Field(default=None, max_length=255)
    host_id: str | None = Field(default=None, max_length=150)

    severity: str | None = Field(default=None, max_length=50)
    synopsis: str | None = None
    description: str | None = None
    plugin_output: str | None = None
    steps_to_remediate: str | None = None

    cvss_v3_base_score: float | None = Field(
        default=None, ge=0, le=10
    )
    cvss_v4_base_score: float | None = Field(
        default=None, ge=0, le=10
    )

    first_discovered: datetime | None = None
    last_observed: datetime | None = None

    repository: str | None = Field(default=None, max_length=255)
    protocol: str | None = Field(default=None, max_length=30)
    port: int | None = Field(default=None, ge=0, le=65535)

    source_payload: dict[str, Any] | None = Field(
        default_factory=dict
    )


class TenableFindingCreate(TenableFindingBase):
    """Schema for manually creating a simulated finding."""

    plugin_id: int = Field(gt=0)
    plugin_name: str = Field(min_length=1, max_length=500)
    cve_ids: list[str] = Field(default_factory=list)

    @field_validator("plugin_name")
    @classmethod
    def validate_plugin_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("plugin_name cannot be blank")
        return value

    @field_validator("cve_ids")
    @classmethod
    def validate_cve_ids(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []

        for value in values:
            cve = value.strip().upper()

            if not cve:
                raise ValueError("CVE identifiers cannot be blank")

            if cve not in normalized:
                normalized.append(cve)

        return normalized


class TenableFindingCVEResponse(BaseModel):
    """CVE association returned for a finding."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    finding_id: int
    cve: str


class TenableFindingResponse(TenableFindingBase):
    """Finding response with access to BRD source-field coverage."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: int
    created_at: datetime
    updated_at: datetime

    cves: list[TenableFindingCVEResponse] = Field(
        default_factory=list
    )

    @computed_field
    @property
    def brd_54_fields(self) -> dict[str, Any]:
        """Return the 54 exact BRD field labels and received values."""
        payload = self.source_payload or {}
        snapshot = payload.get("_brd_54_fields")

        if isinstance(snapshot, dict):
            return snapshot

        return {}

    @computed_field
    @property
    def normalized_cvss_base_score(self) -> float | None:
        """Prefer CVSS V3 base score, falling back to V4."""
        payload = self.source_payload or {}
        metadata = payload.get("_brd_normalization")

        if isinstance(metadata, dict):
            score = metadata.get("normalized_cvss_base_score")

            if isinstance(score, (int, float)) and not isinstance(
                score, bool
            ):
                return float(score)

        # Legacy records without normalizer metadata use the same precedence.
        if self.cvss_v3_base_score is not None:
            return self.cvss_v3_base_score

        return self.cvss_v4_base_score

    @computed_field
    @property
    def actionable(self) -> bool:
        """Informational records remain stored but are not actionable."""
        payload = self.source_payload or {}
        metadata = payload.get("_brd_normalization")

        if isinstance(metadata, dict):
            value = metadata.get("actionable")
            if isinstance(value, bool):
                return value

        severity = (self.severity or "").strip().lower()
        return severity not in {"info", "informational"}


class TenableFindingListResponse(BaseModel):
    """Paginated list of findings."""

    model_config = ConfigDict(extra="forbid")

    items: list[TenableFindingResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50000)
    offset: int = Field(ge=0)
    has_more: bool


class TenableScanBase(BaseModel):
    """Common fields for a Tenable scan."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    source_scan_id: str = Field(min_length=1, max_length=100)
    name: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, max_length=50)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    source_payload: dict[str, Any] | None = Field(default_factory=dict)


class TenableScanCreate(TenableScanBase):
    """Schema for creating a Tenable scan record."""


class TenableScanResponse(TenableScanBase):
    """Schema for returning a Tenable scan record."""

    id: int
    created_at: datetime
    updated_at: datetime


class TenableScanListResponse(BaseModel):
    """Paginated list of Tenable scans."""

    model_config = ConfigDict(extra="forbid")

    items: list[TenableScanResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50000)
    offset: int = Field(ge=0)
    has_more: bool


class TenableImportResponse(BaseModel):
    """Summary of Tenable provider import operation."""

    model_config = ConfigDict(extra="forbid")

    records_received: int
    created: int
    updated: int
    skipped_without_source_identity: int
    informational_records_retained: int
    errors: int
    source_offset: int
    source_limit: int