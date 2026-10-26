"""Pydantic schemas for BMC Helix ITSM changes and worklogs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ITSMChangeBase(BaseModel):
    """Common fields for a BMC Helix ITSM change request."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    source_change_id: str = Field(
        min_length=1,
        max_length=100,
    )

    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)

    status: str | None = Field(default=None, max_length=100)
    impact: str | None = Field(default=None, max_length=50)
    urgency: str | None = Field(default=None, max_length=50)

    location_company: str | None = Field(
        default=None,
        max_length=255,
    )
    detailed_description: str | None = None
    company: str | None = Field(default=None, max_length=255)

    support_organization: str | None = Field(
        default=None,
        max_length=255,
    )
    support_group_name: str | None = Field(
        default=None,
        max_length=255,
    )

    change_nature: str | None = Field(
        default=None,
        max_length=255,
    )
    nature_of_change: str | None = Field(
        default=None,
        max_length=255,
    )
    application_infrastructure: str | None = Field(
        default=None,
        max_length=255,
    )
    downtime_required: str | None = Field(
        default=None,
        max_length=50,
    )

    service_ci: str | None = Field(default=None, max_length=255)
    description: str | None = None
    environment: str | None = Field(default=None, max_length=100)

    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None

    source_payload: dict[str, Any] | None = None

    @field_validator("source_change_id")
    @classmethod
    def validate_source_change_id(cls, value: str) -> str:
        """Reject blank external change identifiers."""
        value = value.strip()

        if not value:
            raise ValueError("source_change_id cannot be blank")

        return value


class ITSMChangeCreate(ITSMChangeBase):
    """Schema for creating a simulated ITSM change request."""


class ITSMChangeUpdate(BaseModel):
    """Schema for updating selected fields of a change request."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)

    status: str | None = Field(default=None, max_length=100)
    impact: str | None = Field(default=None, max_length=50)
    urgency: str | None = Field(default=None, max_length=50)

    location_company: str | None = Field(
        default=None,
        max_length=255,
    )
    detailed_description: str | None = None
    company: str | None = Field(default=None, max_length=255)

    support_organization: str | None = Field(
        default=None,
        max_length=255,
    )
    support_group_name: str | None = Field(
        default=None,
        max_length=255,
    )

    change_nature: str | None = Field(
        default=None,
        max_length=255,
    )
    nature_of_change: str | None = Field(
        default=None,
        max_length=255,
    )
    application_infrastructure: str | None = Field(
        default=None,
        max_length=255,
    )
    downtime_required: str | None = Field(
        default=None,
        max_length=50,
    )

    service_ci: str | None = Field(default=None, max_length=255)
    description: str | None = None
    environment: str | None = Field(default=None, max_length=100)

    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None

    source_payload: dict[str, Any] | None = None


class ITSMChangeResponse(ITSMChangeBase):
    """Schema returned for a persisted change request."""

    id: int
    created_at: datetime
    updated_at: datetime


class ITSMChangeListResponse(BaseModel):
    """Paginated list of ITSM changes."""

    model_config = ConfigDict(extra="forbid")

    items: list[ITSMChangeResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50000)
    offset: int = Field(ge=0)
    has_more: bool


class ITSMWorklogBase(BaseModel):
    """Base fields for an ITSM worklog."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    worklog_type: str | None = Field(default="General Information", max_length=100)
    description: str = Field(min_length=1)
    submitter: str | None = Field(default=None, max_length=255)
    source_worklog_id: str | None = Field(default=None, max_length=100)
    source_payload: dict[str, Any] | None = None


class ITSMWorklogCreate(ITSMWorklogBase):
    """Schema for creating a worklog entry."""


class ITSMWorklogResponse(BaseModel):
    """Schema returned for an ITSM worklog entry."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    id: int
    change_id: int
    source_worklog_id: str | None = None
    worklog_type: str | None = None
    description: str | None = None
    submitter: str | None = None
    source_payload: dict[str, Any] | None = None
    created_at: datetime


class ITSMWorklogListResponse(BaseModel):
    """Paginated list of ITSM worklogs."""

    model_config = ConfigDict(extra="forbid")

    items: list[ITSMWorklogResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50000)
    offset: int = Field(ge=0)
    has_more: bool


class ITSMChangeHistoryResponse(BaseModel):
    """Schema returned for an ITSM change history record."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    id: int
    change_id: int
    action: str
    previous_status: str | None = None
    new_status: str | None = None
    details: str | None = None
    source_payload: dict[str, Any] | None = None
    created_at: datetime


class ITSMChangeHistoryListResponse(BaseModel):
    """Paginated list of ITSM change history."""

    model_config = ConfigDict(extra="forbid")

    items: list[ITSMChangeHistoryResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50000)
    offset: int = Field(ge=0)
    has_more: bool


class ITSMImportResponse(BaseModel):
    """Summary of ITSM provider import operation."""

    model_config = ConfigDict(extra="forbid")

    changes_imported: int
    worklogs_imported: int
    errors: int