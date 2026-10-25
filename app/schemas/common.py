"""Shared API schemas."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class APIResponse(BaseModel):
    """Standard response envelope for API endpoints."""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    message: str = "Request completed successfully"
    data: Any = None


class ErrorResponse(BaseModel):
    """Consistent API error response."""

    model_config = ConfigDict(extra="forbid")

    success: bool = False
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class PaginationParams(BaseModel):
    """Validated pagination parameters."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class PaginatedResponse(BaseModel):
    """Standard paginated response envelope."""

    model_config = ConfigDict(extra="forbid")

    items: list[Any]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)
    has_more: bool