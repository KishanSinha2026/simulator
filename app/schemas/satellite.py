"""Pydantic schemas for Red Hat Satellite hosts and job execution."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SatelliteHostBase(BaseModel):
    """Common fields for a Satellite host."""

    source_id: str | None = Field(default=None, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    operating_system: str | None = Field(default=None, max_length=255)
    os_version: str | None = Field(default=None, max_length=255)
    organization: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    environment: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, max_length=100)
    source_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class SatelliteHostResponse(SatelliteHostBase):
    """Schema returned for a Satellite host."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class SatelliteJobTemplateResponse(BaseModel):
    """Schema returned for a job template."""

    id: int
    source_id: str | None = None
    name: str
    description: str | None = None
    job_category: str | None = None
    effective_user: str | None = None
    source_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class SatelliteJobLaunchRequest(BaseModel):
    """Request to launch a simulated or authorized Satellite job."""

    template_id: str = Field(min_length=1, max_length=255)
    host_ids: list[str] = Field(min_length=1, max_length=100)
    inputs: dict[str, Any] = Field(default_factory=dict)
    approved: bool = False

    model_config = ConfigDict(extra="forbid")


class SatelliteJobRunResponse(BaseModel):
    """Schema returned for a Satellite job run."""

    id: int
    source_id: str | None = None
    template_id: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    source_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class SatelliteJobHostResultResponse(BaseModel):
    """Per-host result for a Satellite job run."""

    id: int
    job_run_id: str
    host_id: str
    status: str
    result: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    source_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class SatelliteJobCancelRequest(BaseModel):
    """Request to cancel a job that is still eligible for cancellation."""

    reason: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")