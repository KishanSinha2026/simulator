"""Pydantic schemas for Tenable vulnerability findings."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TenableFindingBase(BaseModel):
    """Common fields for a Tenable finding."""

    plugin_id: int = Field(gt=0)
    plugin_name: str = Field(min_length=1, max_length=500)
    ip_address: str | None = None
    dns_name: str | None = None
    host_id: str | None = None
    severity: str | None = None
    synopsis: str | None = None
    description: str | None = None
    plugin_output: str | None = None
    solution: str | None = None
    cvss_v3_base_score: float | None = Field(default=None, ge=0, le=10)
    cvss_v4_base_score: float | None = Field(default=None, ge=0, le=10)
    cve_ids: list[str] = Field(default_factory=list)
    first_discovered: datetime | None = None
    last_observed: datetime | None = None
    repository: str | None = None
    protocol: str | None = None
    port: int | None = Field(default=None, ge=0, le=65535)
    source_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("plugin_name")
    @classmethod
    def validate_plugin_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("plugin_name cannot be blank")
        return value


class TenableFindingCreate(TenableFindingBase):
    """Schema for creating a simulated finding."""


class TenableFindingResponse(TenableFindingBase):
    """Schema returned by the API."""

    id: int
    source_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class TenableFindingListResponse(BaseModel):
    """Paginated list of Tenable findings."""

    items: list[TenableFindingResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)
    has_more: bool