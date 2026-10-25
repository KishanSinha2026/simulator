"""Pydantic schemas for ITSM changes and worklogs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ITSMChangeBase(BaseModel):
    """Common fields for an ITSM change request."""

    source_id: str | None = Field(default=None, max_length=255)
    summary: str = Field(min_length=1, max_length=500)
    detailed_description: str | None = None
    status: str | None = Field(default=None, max_length=100)
    impact: int | None = Field(default=None, ge=1, le=5)
    urgency: int | None = Field(default=None, ge=1, le=5)
    priority: int | None = Field(default=None, ge=1, le=5)
    change_type: str | None = Field(default=None, max_length=100)
    assignee_group: str | None = Field(default=None, max_length=255)
    assignee: str | None = Field(default=None, max_length=255)
    service_ci: str | None = Field(default=None, max_length=255)
    environment: str | None = Field(default=None, max_length=100)
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    source_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("summary cannot be blank")
        return value


class ITSMChangeCreate(ITSMChangeBase):
    """Schema for creating a simulated change request."""


class ITSMChangeUpdate(BaseModel):
    """Schema for updating selected change request fields."""

    summary: str | None = Field(default=None, min_length=1, max_length=500)
    detailed_description: str | None = None
    status: str | None = Field(default=None, max_length=100)
    impact: int | None = Field(default=None, ge=1, le=5)
    urgency: int | None = Field(default=None, ge=1, le=5)
    priority: int | None = Field(default=None, ge=1, le=5)
    assignee_group: str | None = Field(default=None, max_length=255)
    assignee: str | None = Field(default=None, max_length=255)
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class ITSMChangeResponse(ITSMChangeBase):
    """Schema returned for a change request."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ITSMWorklogResponse(BaseModel):
    """Schema returned for a worklog entry."""

    id: int
    source_id: str | None = None
    change_id: str | None = None
    description: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    source_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True, extra="forbid")