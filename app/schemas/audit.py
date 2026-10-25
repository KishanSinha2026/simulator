"""Pydantic schemas for synchronization and mock-request audit records."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SyncRunResponse(BaseModel):
    """Schema returned for an integration synchronization run."""

    id: int
    integration: str
    operation: str
    status: str
    records_processed: int = Field(ge=0)
    records_created: int = Field(ge=0)
    records_updated: int = Field(ge=0)
    records_failed: int = Field(ge=0)
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class MockRequestLogResponse(BaseModel):
    """Schema returned for a recorded simulator request."""

    id: int
    integration: str
    method: str
    path: str
    status_code: int = Field(ge=100, le=599)
    request_payload: dict[str, Any] = Field(default_factory=dict)
    response_payload: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float | None = Field(default=None, ge=0)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")