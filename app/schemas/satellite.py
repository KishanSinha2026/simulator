"""Pydantic schemas for Red Hat Satellite resources and job simulation."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

class SatelliteHostBase(BaseModel):
    """Fields for a host registered in Satellite."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    source_host_id: str = Field(
        min_length=1,
        max_length=100,
    )
    name: str = Field(
        min_length=1,
        max_length=255,
    )
    ip_address: str | None = Field(
        default=None,
        max_length=45,
    )
    operating_system: str | None = Field(
        default=None,
        max_length=255,
    )
    organization_id: int | None = None
    location_id: int | None = None
    source_payload: dict[str, Any] | None = None


class SatelliteHostResponse(SatelliteHostBase):
    """Schema returned for a persisted Satellite host."""

    id: int
    created_at: datetime
    updated_at: datetime


class SatelliteJobTemplateResponse(BaseModel):
    """Schema returned for a Satellite job template."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    id: int
    source_template_id: str
    name: str
    description: str | None = None
    template_type: str | None = None
    input_schema: dict[str, Any] | None = None
    source_payload: dict[str, Any] | None = None
    created_at: datetime


class SatelliteJobLaunchRequest(BaseModel):
    """Request to record a simulated Satellite job."""

    model_config = ConfigDict(extra="forbid")

    # External Satellite template ID, not the internal database ID.
    template_id: str = Field(
        min_length=1,
        max_length=100,
    )

    # External Satellite host IDs, resolved by the service.
    host_ids: list[str] = Field(
        min_length=1,
        max_length=100,
    )

    inputs: dict[str, Any] = Field(
        default_factory=dict,
    )

    @classmethod
    def validate_host_ids(cls, values: list[str]) -> list[str]:
        """Validate host identifiers."""
        normalized = [value.strip() for value in values]

        if any(not value for value in normalized):
            raise ValueError("Host IDs cannot be blank")

        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate host IDs are not allowed")

        return normalized
    
    @field_validator("host_ids")
    @classmethod
    def validate_host_ids(cls, values: list[str]) -> list[str]:
        """Validate host identifiers."""
        normalized = [value.strip() for value in values]

        if any(not value for value in normalized):
            raise ValueError("Host IDs cannot be blank")

        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate host IDs are not allowed")

        return normalized


class SatelliteJobRunResponse(BaseModel):
    """Schema returned for a persisted Satellite job run."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    id: int
    source_invocation_id: str | None = None
    template_id: int
    status: str
    inputs: dict[str, Any]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    source_payload: dict[str, Any] | None = None
    created_at: datetime


class SatelliteJobHostResultResponse(BaseModel):
    """Schema returned for one host's job result."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    id: int
    job_run_id: int
    host_id: int
    status: str
    result_text: str | None = None
    source_payload: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class SatelliteJobCancelRequest(BaseModel):
    """Request metadata for cancelling an eligible job."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(
        default=None,
        max_length=1000,
    )